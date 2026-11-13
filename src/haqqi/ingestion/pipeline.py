"""Pipeline d'ingestion : documents → articles.jsonl (avec mises à jour).

Utilisation :
    python -m haqqi.ingestion.pipeline            # ingère les documents nouveaux ou modifiés
    python -m haqqi.ingestion.pipeline --force    # ré-ingère tout
    python -m haqqi.ingestion.pipeline --only ct_ar

Schéma :
    data/sources.json ─┐
    data/raw/*.pdf ────┼→ extraction → découpage par article → métadonnées
                       │
                       └→ comparaison avec l'existant (empreintes) → articles.jsonl
                                                                  → manifest.json
"""

from __future__ import annotations

import argparse
import hashlib
import json
import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path

from .. import config
from .pdf_extract import extract_pages
from .splitter import split_into_articles

log = logging.getLogger(__name__)


@dataclass
class DocReport:
    doc_id: str
    status: str                      # missing | unchanged | ingested
    added: int = 0
    updated: int = 0
    removed: int = 0
    unchanged: int = 0
    n_articles: int = 0


@dataclass
class IngestReport:
    docs: list[DocReport] = field(default_factory=list)
    total_articles: int = 0

    def print(self) -> None:
        print(f"\n{'document':<16}{'statut':<12}{'articles':>9}{'ajoutés':>9}{'modifiés':>10}{'supprimés':>11}")
        print("-" * 67)
        for d in self.docs:
            print(f"{d.doc_id:<16}{d.status:<12}{d.n_articles:>9}{d.added:>9}{d.updated:>10}{d.removed:>11}")
        print(f"\nTotal dans l'index : {self.total_articles} articles")


# --- Lecture / écriture ----------------------------------------------------------
def load_sources(path: Path) -> list[dict]:
    return json.loads(path.read_text(encoding="utf-8"))["documents"]


def find_source_file(raw_dir: Path, stem: str) -> Path | None:
    """Cherche data/raw/<stem>.pdf puis data/raw/<stem>.txt."""
    for ext in config.SUPPORTED_EXTENSIONS:
        candidate = raw_dir / f"{stem}{ext}"
        if candidate.exists():
            return candidate
    return None


def file_sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load_store(path: Path) -> dict[str, dict]:
    if not path.exists():
        return {}
    records = {}
    with path.open(encoding="utf-8") as f:
        for line in f:
            if line.strip():
                rec = json.loads(line)
                records[rec["id"]] = rec
    return records


def save_store(path: Path, records: dict[str, dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    ordered = sorted(records.values(), key=lambda r: (r["doc_id"], _sort_key(r["article"])))
    with path.open("w", encoding="utf-8") as f:
        for rec in ordered:
            f.write(json.dumps(rec, ensure_ascii=False) + "\n")


def _sort_key(article: str) -> tuple:
    """Trie « 2 » avant « 10 » et « 6-4 » après « 6 »."""
    parts = []
    for chunk in article.replace("#", "-").split("-"):
        digits = "".join(c for c in chunk if c.isdigit())
        parts.append((int(digits) if digits else 0, chunk))
    return tuple(parts)


def load_manifest(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}


def save_manifest(path: Path, manifest: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")


# --- Versions : quel article est « en vigueur » ? -------------------------------
def mark_current_versions(records: dict[str, dict]) -> None:
    """Pour chaque (article, langue), la version la plus récente est « en vigueur ».

    Exemple : ct:6-4 en arabe existe dans l'édition 2004 ET dans la loi 2025-9
    → la loi 2025-9 est en vigueur, l'édition 2004 est marquée remplacée.

    Cas particuliers :
    - remplacement d'un seul paragraphe (« الفقرة الأولى (جديدة) ») : la nouvelle
      version est en vigueur, mais l'ancien article aussi (pour ses autres paragraphes).
    - article abrogé (« ألغي بالقانون … ») : plus en vigueur, ``replaced_by = "abrogé"``.
    - loi modificative disponible dans une seule langue : la loi 2025-9 n'existe qu'en
      arabe, mais elle remplace AUSSI le texte français de l'article (``replaced_lang = "ar"``).
    """
    groups: dict[tuple[str, str], list[dict]] = {}
    for rec in records.values():
        groups.setdefault((rec["article_key"], rec["lang"]), []).append(rec)

    for recs in groups.values():
        full = [r for r in recs if not r.get("paragraph")]
        partial = [r for r in recs if r.get("paragraph")]
        for rec in partial:
            rec["is_current"], rec["replaced_by"] = True, None
        if not full:
            continue
        latest = max(full, key=lambda r: (r.get("date") or "", r["doc_id"].startswith("loi")))
        for rec in full:
            rec["is_current"] = rec is latest
            rec["replaced_by"] = None if rec is latest else latest["version"]
        if latest.get("status") == "abrogé":
            latest["is_current"], latest["replaced_by"] = False, "abrogé"

    # Remplacement venu d'une autre langue
    latest_law: dict[str, dict] = {}
    for rec in records.values():
        if rec.get("source_kind") == "amending_law" and not rec.get("paragraph"):
            best = latest_law.get(rec["article_key"])
            if best is None or (rec.get("date") or "") > (best.get("date") or ""):
                latest_law[rec["article_key"]] = rec
    for rec in records.values():
        law = latest_law.get(rec["article_key"])
        if (law and rec["is_current"] and rec["lang"] != law["lang"]
                and rec.get("source_kind") != "amending_law" and not rec.get("paragraph")
                and (rec.get("date") or "") < (law.get("date") or "")):
            rec["is_current"], rec["replaced_by"], rec["replaced_lang"] = False, law["version"], law["lang"]


# --- Pipeline -------------------------------------------------------------------
def ingest(
    sources_file: Path = config.SOURCES_FILE,
    raw_dir: Path = config.RAW_DIR,
    articles_file: Path = config.ARTICLES_FILE,
    manifest_file: Path = config.MANIFEST_FILE,
    only: list[str] | None = None,
    force: bool = False,
) -> IngestReport:
    sources = load_sources(sources_file)
    store = load_store(articles_file)
    manifest = load_manifest(manifest_file)
    report = IngestReport()
    now = datetime.now(timezone.utc).isoformat(timespec="seconds")

    for source in sources:
        doc_id = source["doc_id"]
        if only and doc_id not in only:
            continue

        path = find_source_file(raw_dir, source["file"])
        if path is None:
            log.warning("%s : fichier introuvable (%s.pdf ou .txt dans %s)", doc_id, source["file"], raw_dir)
            report.docs.append(DocReport(doc_id, "missing"))
            continue

        sha = file_sha256(path)
        if not force and manifest.get(doc_id, {}).get("sha256") == sha:
            n = sum(1 for r in store.values() if r["doc_id"] == doc_id)
            report.docs.append(DocReport(doc_id, "unchanged", n_articles=n, unchanged=n))
            continue

        pages = extract_pages(path, lang=source["lang"])
        articles = split_into_articles(pages, {**source, "_path": path.name})
        new_records = {a.id: a.to_record() for a in articles}
        old_ids = {rid for rid, r in store.items() if r["doc_id"] == doc_id}

        doc = DocReport(doc_id, "ingested", n_articles=len(new_records))
        for rid, rec in new_records.items():
            old = store.get(rid)
            if old is None:
                doc.added += 1
                rec["ingested_at"] = now
            elif old["hash"] != rec["hash"]:
                doc.updated += 1
                rec["ingested_at"] = now
            else:
                doc.unchanged += 1
                rec["ingested_at"] = old.get("ingested_at", now)
            store[rid] = rec
        for rid in old_ids - new_records.keys():
            doc.removed += 1
            del store[rid]

        manifest[doc_id] = {
            "file": path.name,
            "sha256": sha,
            "pages": len(pages),
            "n_articles": len(new_records),
            "ingested_at": now,
        }
        report.docs.append(doc)

    mark_current_versions(store)
    save_store(articles_file, store)
    save_manifest(manifest_file, manifest)
    report.total_articles = len(store)
    return report


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description="Ingestion des textes de loi → articles.jsonl")
    parser.add_argument("--force", action="store_true", help="ré-ingérer même si le fichier n'a pas changé")
    parser.add_argument("--only", nargs="+", metavar="DOC_ID", help="ingérer seulement ces documents")
    args = parser.parse_args(argv)

    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    report = ingest(only=args.only, force=args.force)
    report.print()


if __name__ == "__main__":
    main()