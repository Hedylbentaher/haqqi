"""Poser une question à Haqqi depuis le terminal.

    python -m haqqi.agent.ask "Quel est l'âge minimum pour travailler ?"
    python -m haqqi.agent.ask "ما هي المدة القصوى لفترة التجربة؟" --no-llm
    python -m haqqi.agent.ask "What changed in article 6-4 in 2025?" --embedder hash
"""

from __future__ import annotations

import argparse
import logging

from ..retrieval.embeddings import VectorIndex, get_embedder
from ..retrieval.hybrid import Retriever
from ..retrieval.store import ArticleStore
from .graph import HaqqiAgent


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description="Poser une question à Haqqi")
    parser.add_argument("question")
    parser.add_argument("--no-llm", action="store_true", help="réponse extractive, sans modèle de langage")
    parser.add_argument("--embedder", choices=["e5", "hash"], default=None)
    parser.add_argument("--mode", choices=["bm25", "vector", "hybrid"], default="hybrid")
    args = parser.parse_args(argv)
    logging.basicConfig(level=logging.WARNING, format="%(levelname)s %(message)s")

    store = ArticleStore.load()
    index, _ = VectorIndex.build(store.records, get_embedder(args.embedder) if args.embedder else get_embedder())
    agent = HaqqiAgent(Retriever(store, index), llm=None if args.no_llm else "auto", mode=args.mode)
    out = agent.ask(args.question)

    print(f"\nLangue : {out['language']} · chemin : {out['route']} · LLM : {agent.llm_name}\n")
    print(out["answer"])
    print("\nSources :")
    for c in out["citations"]:
        state = "en vigueur" if c["is_current"] else f"remplacé ({c['replaced_by']})"
        print(f"  [{c['article_key']}] {c['label']} — {c['version']}, {c['lang']}, {state}, page {c['page']}")
    for w in out.get("warnings", []):
        print(f"⚠ {w}")


if __name__ == "__main__":
    main()