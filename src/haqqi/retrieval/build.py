"""Construire l'index et essayer une recherche.

    python -m haqqi.retrieval.build                       # calcule / met à jour les vecteurs
    python -m haqqi.retrieval.build --search "âge minimum pour travailler"
    python -m haqqi.retrieval.build --search "minimum age" --mode bm25 --lang en
    python -m haqqi.retrieval.build --embedder hash       # sans télécharger le modèle
"""

from __future__ import annotations

import argparse
import time

from .embeddings import VectorIndex, get_embedder
from .hybrid import MODES, Retriever
from .store import ArticleStore, citation_label


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description="Index de recherche Haqqi")
    parser.add_argument("--embedder", choices=["e5", "hash"], default=None,
                        help="e5 = modèle multilingue (défaut), hash = sans téléchargement")
    parser.add_argument("--search", metavar="QUESTION")
    parser.add_argument("--mode", choices=MODES, default="hybrid")
    parser.add_argument("--lang", choices=["ar", "fr", "en"], default=None, help="langue des documents")
    parser.add_argument("--all-versions", action="store_true", help="inclure les versions remplacées")
    parser.add_argument("-k", type=int, default=5)
    args = parser.parse_args(argv)

    store = ArticleStore.load()
    embedder = get_embedder(args.embedder) if args.embedder else get_embedder()
    t0 = time.time()
    index, report = VectorIndex.build(store.records, embedder)
    print(f"Index : {len(store)} fiches · modèle {embedder.name} · "
          f"{report.embedded} calculées, {report.reused} reprises du cache, "
          f"{report.removed} supprimées · {time.time() - t0:.1f} s")

    if args.search:
        retriever = Retriever(store, index)
        hits = retriever.search(args.search, k=args.k, mode=args.mode, lang=args.lang,
                                current_only=not args.all_versions)
        print(f"\nQuestion : {args.search}  (mode {args.mode})\n")
        for n, h in enumerate(hits, 1):
            ranks = ", ".join(f"{k} #{v}" for k, v in h.ranks.items())
            print(f"{n}. {citation_label(h.record)}  [{ranks}]")
            print(f"   {h.record['text'][:160].replace(chr(10), ' ')}…")


if __name__ == "__main__":
    main()