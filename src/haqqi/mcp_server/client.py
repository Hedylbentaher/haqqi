"""Client MCP de démonstration : lance le serveur, liste ses outils et les appelle.

    python -m haqqi.mcp_server.client
    python -m haqqi.mcp_server.client --question "ما هي السن الدنيا للتشغيل؟"
"""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import sys

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client


def server_params() -> StdioServerParameters:
    return StdioServerParameters(command=sys.executable, args=["-m", "haqqi.mcp_server.server"],
                                 env=dict(os.environ))


def _payload(result) -> object:
    """Contenu d'un résultat d'outil MCP (structuré si possible, sinon texte JSON)."""
    if getattr(result, "structuredContent", None):
        data = result.structuredContent
        return data.get("result", data) if isinstance(data, dict) else data
    texts = [c.text for c in result.content if getattr(c, "type", "") == "text"]
    try:
        return json.loads(texts[0]) if len(texts) == 1 else [json.loads(t) for t in texts]
    except (json.JSONDecodeError, IndexError):
        return "\n".join(texts)


async def demo(question: str) -> dict:
    async with stdio_client(server_params()) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()
            tools = (await session.list_tools()).tools
            print(f"Outils du serveur MCP « haqqi » ({len(tools)}) :")
            for t in tools:
                print(f"  • {t.name} — {t.description.splitlines()[0]}")

            print(f"\n① search_by_language(query={question!r}, doc_language='ar')")
            hits = _payload(await session.call_tool("search_by_language",
                                                    {"query": question, "doc_language": "ar", "k": 3}))
            for h in hits:
                print(f"   [{h['article_key']}] {h['version']} ({h['lang']}) — {h['text'][:90]}…")
            if not hits:
                print("   (aucun résultat : sans le modèle multilingue, la recherche français → arabe est impossible)")

            print("\n② compare_versions(article_key='ct:6-4')")
            for v in _payload(await session.call_tool("compare_versions", {"article_key": "ct:6-4"})):
                print(f"   {v['lang']} · {v['version']} · {'EN VIGUEUR' if v['is_current'] else 'remplacé'}")

            print(f"\n③ answer_with_citations(question={question!r})")
            answer = _payload(await session.call_tool("answer_with_citations", {"question": question}))
            print(f"   ({answer['language']}, chemin {answer['route']}, LLM : {answer['llm']})")
            print("   " + answer["answer"].replace("\n", "\n   "))
            print("   Sources : " + ", ".join(c["article_key"] for c in answer["citations"]))
            return {"tools": [t.name for t in tools], "hits": hits, "answer": answer}


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description="Démonstration du serveur MCP Haqqi")
    parser.add_argument("--question", default="Quel est l'âge minimum pour travailler en Tunisie ?")
    args = parser.parse_args(argv)
    asyncio.run(demo(args.question))


if __name__ == "__main__":
    main()