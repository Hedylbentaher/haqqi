"""Affiche un article dans toutes ses langues et versions (outil de vérification).

Utilisation :
    python -m haqqi.ingestion.show 6-4        # l'article 6-4 en AR / FR, toutes versions
    python -m haqqi.ingestion.show --stats    # nombre d'articles par document
"""

from __future__ import annotations

import argparse
from collections import Counter

from .. import config
from .pipeline import load_store


def show_article(number: str) -> None:
    store = load_store(config.ARTICLES_FILE)
    matches = [r for r in store.values() if r["article"] == number]
    if not matches:
        print(f"Aucun article « {number} » dans l'index. Lancez d'abord le pipeline.")
        return
    for r in sorted(matches, key=lambda r: (r["code"], r["lang"], r.get("date") or "")):
        state = "EN VIGUEUR" if r["is_current"] else f"remplacé par {r['replaced_by']}"
        print("=" * 70)
        print(f"{r['article_key']} | {r['lang']} | {r['version']} | {state} | page {r['page']}")
        if r["section"]:
            print(f"Section : {r['section']}")
        print("-" * 70)
        print(r["text"][:800] + ("…" if len(r["text"]) > 800 else ""))


def show_stats() -> None:
    store = load_store(config.ARTICLES_FILE)
    by_doc = Counter(r["doc_id"] for r in store.values())
    by_code = Counter((r["code"], r["lang"]) for r in store.values())
    current = sum(1 for r in store.values() if r["is_current"])
    print("Articles par document :")
    for doc, n in sorted(by_doc.items()):
        print(f"  {doc:<16}{n:>6}")
    print("Articles par texte et langue :")
    for (code, lang), n in sorted(by_code.items()):
        print(f"  {code:<16}{lang:<4}{n:>6}")
    print(f"En vigueur : {current} / {len(store)}")


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description="Vérifier le contenu de l'index d'articles")
    parser.add_argument("article", nargs="?", help="numéro d'article, ex. 6-4 ou 234bis")
    parser.add_argument("--stats", action="store_true")
    args = parser.parse_args(argv)
    if args.stats or not args.article:
        show_stats()
    else:
        show_article(args.article)


if __name__ == "__main__":
    main()