"""Les fonctions « métier » de Haqqi, partagées par le serveur MCP et l'interface web.

    search_by_language   → chercher des articles (filtre de langue facultatif)
    get_article          → lire un article dans toutes ses langues
    compare_versions     → toutes les versions d'un article (avant / après 2025)
    answer_with_citations→ poser une question à l'agent LangGraph
    ingest_document      → ajouter un nouveau document au corpus (mise à jour de l'index)
"""

from __future__ import annotations

import json
import shutil
from functools import lru_cache
from pathlib import Path

from . import config
from .agent.graph import HaqqiAgent, expand_abbreviations, label_for
from .ingestion.pipeline import ingest
from .retrieval.embeddings import HashEmbedder, VectorIndex, get_embedder
from .retrieval.hybrid import Retriever
from .retrieval.store import ArticleStore

LANGS = ("ar", "fr", "en")
KINDS = ("code", "amending_law", "convention")


@lru_cache(maxsize=1)
def get_agent() -> HaqqiAgent:
    """Charge une seule fois les fiches, l'index et le modèle de langage."""
    store = ArticleStore.load(config.ARTICLES_FILE)
    index, _ = VectorIndex.build(store.records, get_embedder(config.EMBEDDER), cache=config.VECTORS_FILE)
    return HaqqiAgent(Retriever(store, index))


def _short(rec: dict, lang: str = "fr", max_chars: int = 700) -> dict:
    text = " ".join(rec["text"].split())
    return {
        "article_key": rec["article_key"],
        "label": label_for(rec, lang),
        "lang": rec["lang"],
        "version": rec["version"],
        "is_current": bool(rec.get("is_current")),
        "replaced_by": rec.get("replaced_by"),
        "page": rec.get("page"),
        "document": rec.get("title", ""),
        "text": text if len(text) <= max_chars else text[:max_chars] + " …",
    }


def search_by_language(query: str, doc_language: str = "", k: int = 5,
                       include_old_versions: bool = False) -> list[dict]:
    if doc_language and doc_language not in LANGS:
        raise ValueError(f"doc_language doit être ar, fr, en ou vide (reçu : {doc_language})")
    agent = get_agent()
    retriever = agent.retriever
    mode = "hybrid"
    if retriever.vectors is None or isinstance(retriever.vectors.embedder, HashEmbedder):
        mode = "bm25"
    hits = retriever.search(expand_abbreviations(query), k=k, mode=mode, lang=doc_language or None,
                            current_only=not include_old_versions)
    return [_short(h.record) | _history(retriever.store, h.article_key)
            | {"score": round(h.score, 4), "ranks": h.ranks} for h in hits]


def _history(store: ArticleStore, article_key: str) -> dict:
    """Combien de versions a l'article, et quelle loi l'a modifié (signal pour l'agent à outils)."""
    versions = store.versions(article_key)
    laws = sorted({v["version"] for v in versions if v.get("source_kind") == "amending_law"})
    return {"n_versions": len(versions), "changed_by": laws}


def get_article(article_key: str, lang: str = "") -> list[dict]:
    store = get_agent().retriever.store
    recs = [r for r in store.versions(article_key) if not lang or r["lang"] == lang]
    if not recs:
        raise ValueError(f"Article inconnu : {article_key} (exemples : ct:53, ct:6-4, c138:2)")
    return [_short(r, max_chars=4000) for r in recs]


def compare_versions(article_key: str) -> list[dict]:
    versions = get_article(article_key)
    return sorted(versions, key=lambda v: (v["lang"], not v["is_current"]))


def answer_with_citations(question: str) -> dict:
    agent = get_agent()
    out = agent.ask(question)
    return {
        "answer": out["answer"],
        "language": out["language"],
        "route": out["route"],
        "llm": agent.llm_name,
        "citations": [{k: c[k] for k in ("article_key", "label", "lang", "version", "is_current", "page")}
                      for c in out["citations"]],
        "warnings": out.get("warnings", []),
    }


def ingest_document(path: str, doc_id: str, lang: str, title: str, kind: str = "code", code: str = "",
                    version: str = "v1", date: str = "", target_code: str = "ct") -> dict:
    """Ajoute (ou met à jour) un document : copie dans data/raw, catalogue, découpage, index."""
    src = Path(path)
    if not src.exists():
        raise FileNotFoundError(f"Fichier introuvable : {path}")
    if src.suffix.lower() not in config.SUPPORTED_EXTENSIONS:
        raise ValueError(f"Format non supporté : {src.suffix} (pdf ou txt)")
    if lang not in LANGS or kind not in KINDS:
        raise ValueError(f"lang ∈ {LANGS}, kind ∈ {KINDS}")

    target = config.RAW_DIR / f"{doc_id}{src.suffix.lower()}"
    if src.resolve() != target.resolve():
        config.RAW_DIR.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(src, target)

    catalog = json.loads(config.SOURCES_FILE.read_text(encoding="utf-8"))
    entry = {"doc_id": doc_id, "file": doc_id, "lang": lang, "kind": kind, "code": code or doc_id,
             "version": version, "date": date, "title": title, "source": str(src.name)}
    if kind == "amending_law":
        entry["target_code"] = target_code
    catalog["documents"] = [d for d in catalog["documents"] if d["doc_id"] != doc_id] + [entry]
    config.SOURCES_FILE.write_text(json.dumps(catalog, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    report = ingest(sources_file=config.SOURCES_FILE, raw_dir=config.RAW_DIR, articles_file=config.ARTICLES_FILE,
                    manifest_file=config.MANIFEST_FILE, only=[doc_id])
    doc = report.docs[0]
    get_agent.cache_clear()                       # recharge les fiches…
    store = ArticleStore.load(config.ARTICLES_FILE)
    _, vec = VectorIndex.build(store.records, get_embedder(config.EMBEDDER),   # …et ne calcule que
                               cache=config.VECTORS_FILE)                     # les nouveaux vecteurs
    return {"doc_id": doc_id, "status": doc.status, "articles": doc.n_articles, "added": doc.added,
            "updated": doc.updated, "removed": doc.removed, "vectors_computed": vec.embedded,
            "total_articles": report.total_articles}