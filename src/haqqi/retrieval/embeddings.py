"""Vecteurs multilingues : la recherche par le SENS, dans toutes les langues.

Un modèle d'embeddings transforme un texte en une liste de nombres (un vecteur).
Deux textes qui veulent dire la même chose ont des vecteurs proches,
même s'ils sont dans deux langues différentes :

    « âge minimum pour travailler »  ─┐
    « السن الدنيا للتشغيل »           ├─→ vecteurs proches → cosinus élevé
    « minimum age for employment »   ─┘

Modèle utilisé : intfloat/multilingual-e5-small (≈ 470 Mo, téléchargé une fois).
Les vecteurs des articles sont gardés dans data/index/vectors.npz : seuls les
articles nouveaux ou modifiés (empreinte différente) sont recalculés.
"""

from __future__ import annotations

import logging
import zlib
from dataclasses import dataclass
from pathlib import Path

import numpy as np

from .. import config
from ..ingestion.text_utils import normalize_for_search

log = logging.getLogger(__name__)


# --- Les modèles -------------------------------------------------------------------------
class E5Embedder:
    """Le vrai modèle multilingue (sentence-transformers).

    Les modèles E5 demandent un préfixe : « query: » pour une question,
    « passage: » pour un texte à retrouver.
    """

    def __init__(self, model_name: str = config.EMBEDDING_MODEL, model=None):
        self.name = model_name
        if model is None:
            from sentence_transformers import SentenceTransformer  # import lourd : seulement ici
            model = SentenceTransformer(model_name)
        self.model = model

    def _encode(self, texts: list[str]) -> np.ndarray:
        vecs = self.model.encode(texts, batch_size=32, normalize_embeddings=True,
                                 show_progress_bar=len(texts) > 64)
        return np.asarray(vecs, dtype=np.float32)

    def encode_queries(self, texts: list[str]) -> np.ndarray:
        return self._encode([f"query: {t}" for t in texts])

    def encode_passages(self, texts: list[str]) -> np.ndarray:
        return self._encode([f"passage: {t}" for t in texts])


class HashEmbedder:
    """Modèle simple, sans téléchargement : trigrammes de lettres « hachés » dans 512 cases.

    Il ne comprend PAS les traductions (« congé » ≠ « عطلة »). Il sert aux tests
    et au dépannage quand le vrai modèle n'est pas disponible.
    """

    name = "hash-trigrams-512"

    def __init__(self, dim: int = 512):
        self.dim = dim

    def _vec(self, text: str) -> np.ndarray:
        v = np.zeros(self.dim, dtype=np.float32)
        t = f"  {normalize_for_search(text)}  "
        for i in range(len(t) - 2):
            v[zlib.crc32(t[i:i + 3].encode("utf-8")) % self.dim] += 1.0
        n = np.linalg.norm(v)
        return v / n if n else v

    def encode_queries(self, texts: list[str]) -> np.ndarray:
        return np.stack([self._vec(t) for t in texts]) if texts else np.zeros((0, self.dim), np.float32)

    encode_passages = encode_queries


def get_embedder(kind: str = config.EMBEDDER):
    """« e5 » (par défaut) ou « hash »."""
    if kind == "hash":
        return HashEmbedder()
    return E5Embedder()


def passage_text(rec: dict) -> str:
    """Le texte donné au modèle pour un article : section + texte."""
    head = rec.get("section") or ""
    return f"{head}\n{rec['text']}".strip()[:2000]


# --- L'index de vecteurs ------------------------------------------------------------------
@dataclass
class BuildReport:
    reused: int = 0
    embedded: int = 0
    removed: int = 0


class VectorIndex:
    def __init__(self, ids: list[str], vectors: np.ndarray, embedder):
        self.ids = ids
        self.vectors = vectors
        self.embedder = embedder

    @classmethod
    def build(cls, records: list[dict], embedder, cache: Path | None = config.VECTORS_FILE
              ) -> tuple["VectorIndex", BuildReport]:
        """Calcule les vecteurs des articles, en réutilisant le cache quand le texte n'a pas changé."""
        report = BuildReport()
        cached: dict[tuple[str, str], np.ndarray] = {}
        if cache is not None and cache.exists():
            data = np.load(cache, allow_pickle=False)
            if str(data["model"]) == embedder.name:
                for i, (rid, h) in enumerate(zip(data["ids"], data["hashes"])):
                    cached[(str(rid), str(h))] = data["vectors"][i]
            else:
                log.info("Cache créé avec un autre modèle (%s) : on recalcule tout.", data["model"])

        todo = [r for r in records if (r["id"], r["hash"]) not in cached]
        if todo:
            new_vecs = embedder.encode_passages([passage_text(r) for r in todo])
            for r, v in zip(todo, new_vecs):
                cached[(r["id"], r["hash"])] = v
        report.embedded = len(todo)
        report.reused = len(records) - len(todo)
        wanted = {(r["id"], r["hash"]) for r in records}
        report.removed = sum(1 for k in cached if k not in wanted)

        ids = [r["id"] for r in records]
        dim = next(iter(cached.values())).shape[0] if cached else 0
        vectors = (np.stack([cached[(r["id"], r["hash"])] for r in records]).astype(np.float32)
                   if records else np.zeros((0, dim), np.float32))
        if cache is not None:
            cache.parent.mkdir(parents=True, exist_ok=True)
            np.savez(cache, ids=np.array(ids), hashes=np.array([r["hash"] for r in records]),
                     vectors=vectors, model=np.array(embedder.name))
        return cls(ids, vectors, embedder), report

    def scores(self, query: str) -> np.ndarray:
        """Cosinus entre la question et chaque article (les vecteurs sont déjà normalisés)."""
        q = self.embedder.encode_queries([query])[0]
        return self.vectors @ q