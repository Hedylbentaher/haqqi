"""Recherche hybride : BM25 + vecteurs, fusionnés par RRF (Reciprocal Rank Fusion).

Chaque méthode donne un classement. RRF additionne des points selon le RANG :

┌───────────────────────────────────────────────────────┐
│ RRF(article) = Σ   1 / (60 + rang de l'article)       │
│              méthodes                                  │
└───────────────────────────────────────────────────────┘

Exemple : article classé 1er par BM25 et 3e par les vecteurs
    → 1/61 + 1/63 = 0,0164 + 0,0159 = 0,0323
On utilise le rang et pas le score, car les scores BM25 (0 à 30)
et les cosinus (−1 à 1) ne sont pas sur la même échelle.

Amélioration (étape 6.5) : BM25 selon la langue de la question
BM25 ne trouve que des mots IDENTIQUES, donc des textes de la même langue.
Si la langue de la question représente moins de 10 % des textes cherchés
(anglais : 18 fiches sur 1 070, la seule Convention 138), BM25 ramène
toujours les mêmes articles et ajoute du bruit → on garde les vecteurs seuls.

    mode "hybrid"       : BM25 + vecteurs, BM25 ignoré si la langue est rare
    mode "hybrid_fixed" : BM25 + vecteurs toujours (l'ancienne version, pour comparer)
"""

from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np

from ..ingestion.text_utils import detect_language
from .bm25 import BM25Index
from .embeddings import VectorIndex, get_embedder
from .store import ArticleStore

RRF_K = 60
MIN_LANG_SHARE = 0.10   # BM25 n'est utilisé que si ≥ 10 % des textes sont dans la langue de la question
MODES = ("bm25", "vector", "hybrid_fixed", "hybrid")


@dataclass
class Hit:
    record: dict
    score: float
    ranks: dict = field(default_factory=dict)   # {"bm25": 3, "vector": 1}

    @property
    def article_key(self) -> str:
        return self.record["article_key"]


class Retriever:
    def __init__(self, store: ArticleStore, vector_index: VectorIndex | None = None):
        self.store = store
        self.records = store.records
        self.bm25 = BM25Index([r["text"] for r in self.records])
        self.vectors = vector_index
        self.langs = np.array([r["lang"] for r in self.records])

    @classmethod
    def load(cls, embedder: str | None = None) -> "Retriever":
        """Charge les fiches et l'index de vecteurs (calculé ou repris du cache)."""
        from .. import config
        store = ArticleStore.load(config.ARTICLES_FILE)
        emb = get_embedder(embedder or config.EMBEDDER)
        index, _ = VectorIndex.build(store.records, emb, cache=config.VECTORS_FILE)
        return cls(store, index)

    # ------------------------------------------------------------------------------------
    def _allowed(self, lang: str | None, current_only: bool, code: str | None) -> np.ndarray:
        mask = np.ones(len(self.records), dtype=bool)
        for i, r in enumerate(self.records):
            if lang and r["lang"] != lang:
                mask[i] = False
            elif current_only and not r.get("is_current"):
                mask[i] = False
            elif code and r["code"] != code:
                mask[i] = False
            elif not r["text"].strip():
                mask[i] = False
        return mask

    @staticmethod
    def _ranking(scores: np.ndarray, mask: np.ndarray, positive_only: bool) -> list[int]:
        idx = np.where(mask & (scores > 0) if positive_only else mask)[0]
        return [int(i) for i in idx[np.argsort(-scores[idx], kind="stable")]]

    def bm25_useful(self, query: str, mask: np.ndarray) -> bool:
        """BM25 est-il utile ? Oui si ≥ 10 % des textes cherchés sont dans la langue de la question.

        Exemple (1 070 fiches) : arabe 50 % → oui · français 48 % → oui · anglais 2 % → non.
        Avec le filtre lang="en" (textes anglais seulement), l'anglais fait 100 % → oui.
        """
        if not mask.any():
            return False
        share = float(np.mean(self.langs[mask] == detect_language(query)))
        return share >= MIN_LANG_SHARE

    def search(self, query: str, k: int = 5, mode: str = "hybrid", lang: str | None = None,
               current_only: bool = True, code: str | None = None, depth: int = 50) -> list[Hit]:
        """Les ``k`` meilleures fiches pour la question.

        lang : langue des DOCUMENTS (None = toutes) · current_only : versions en vigueur
        seulement · code : « ct », « c138 »… · depth : taille des listes fusionnées par RRF.
        """
        if mode not in MODES:
            raise ValueError(f"mode inconnu : {mode} (choix : {MODES})")
        if mode != "bm25" and self.vectors is None:
            raise RuntimeError("Pas d'index de vecteurs : utilisez mode='bm25' ou chargez un modèle.")
        mask = self._allowed(lang, current_only, code)
        use_bm25 = mode in ("bm25", "hybrid_fixed") or (mode == "hybrid" and self.bm25_useful(query, mask))
        rankings: dict[str, list[int]] = {}
        if use_bm25:
            rankings["bm25"] = self._ranking(np.array(self.bm25.scores(query)), mask, True)[:depth]
        if mode != "bm25":
            rankings["vector"] = self._ranking(self.vectors.scores(query), mask, False)[:depth]

        fused: dict[int, Hit] = {}
        for name, ranking in rankings.items():
            for rank, i in enumerate(ranking, start=1):
                hit = fused.setdefault(i, Hit(self.records[i], 0.0))
                hit.score += 1.0 / (RRF_K + rank)
                hit.ranks[name] = rank
        return sorted(fused.values(), key=lambda h: -h.score)[:k]

    def search_keys(self, query: str, k: int = 5, **kw) -> list[str]:
        """Classement par ARTICLE (clé), toutes langues confondues : sert à l'évaluation.

        ct:53 en arabe et ct:53 en français comptent pour un seul article.
        """
        keys: list[str] = []
        for hit in self.search(query, k=max(k * 4, 20), **kw):
            if hit.article_key not in keys:
                keys.append(hit.article_key)
            if len(keys) == k:
                break
        return keys