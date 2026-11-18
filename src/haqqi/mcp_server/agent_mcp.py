"""Agent à appel d'outils (tool calling) branché sur le serveur MCP.

Ici, c'est le LLM qui DÉCIDE quels outils appeler, et dans quel ordre :

    question → LLM → « j'appelle search_by_language(…) » → serveur MCP → résultats
                   → LLM → « j'appelle compare_versions(ct:6-4) » → …
                   → LLM → réponse finale avec citations

Outils chargés depuis le serveur MCP avec langchain-mcp-adapters,
agent construit avec LangChain (create_agent, qui tourne sur LangGraph). Il faut une clé API (.env).

    python -m haqqi.mcp_server.agent_mcp "Qu'est-ce qui a changé pour les CDD en 2025 ?"
"""

from __future__ import annotations

import argparse
import asyncio
import os
import sys

from langchain.agents import create_agent
from langchain_mcp_adapters.client import MultiServerMCPClient
from langchain_mcp_adapters.tools import load_mcp_tools

from ..agent.graph import _CITE
from ..agent.llm import get_chat_model

PROMPT = """Tu es Haqqi, un assistant sur le droit du travail tunisien.
Utilise les outils pour trouver les articles AVANT de répondre :
- search_by_language pour chercher (laisse doc_language vide pour chercher dans toutes les langues) ;
- get_article si un article précis est demandé.
Si la question porte sur un changement (réforme, loi 2025-9, « avant / après », « qu'est-ce qui a changé ») :
- appelle compare_versions sur chaque article trouvé dont le champ changed_by n'est pas vide, AVANT de répondre ;
- ne dis jamais qu'il n'y a « aucun changement » sans avoir appelé compare_versions.
Les articles peuvent être en arabe : lis-les et réponds quand même dans la langue de la question.
Cite les clés d'articles entre crochets, ex. [ct:6-4]. N'invente rien : si les outils ne trouvent rien, dis-le."""


def mcp_client() -> MultiServerMCPClient:
    return MultiServerMCPClient({
        "haqqi": {"command": sys.executable, "args": ["-m", "haqqi.mcp_server.server"],
                  "transport": "stdio", "env": dict(os.environ)},
    })


async def run(question: str, llm=None) -> dict:
    llm = llm or get_chat_model()
    if llm is None:
        raise SystemExit("Cet agent a besoin d'un LLM : ajoutez GOOGLE_API_KEY (ou GROQ_API_KEY) dans .env.")
    # Une seule session : le serveur (et le modèle e5) est chargé une fois pour toute la question.
    async with mcp_client().session("haqqi") as session:
        tools = await load_mcp_tools(session)
        agent = create_agent(llm, tools, system_prompt=PROMPT)
        result = await agent.ainvoke({"messages": [("user", question)]})
    calls = [(tc["name"], tc["args"]) for m in result["messages"] for tc in (getattr(m, "tool_calls", None) or [])]
    answer, warnings = verify_citations(result["messages"][-1].text, result["messages"])
    return {"answer": answer, "tool_calls": calls, "messages": result["messages"], "warnings": warnings}


def verify_citations(answer: str, messages: list) -> tuple[str, list[str]]:
    """Comme la case « vérification » du graphe : une clé citée doit venir des résultats des outils."""
    seen = " ".join(str(m.content) for m in messages if getattr(m, "type", "") == "tool")
    warnings = []
    for key in set(_CITE.findall(answer)):
        if f'"{key}"' not in seen and f"'{key}'" not in seen:
            answer = answer.replace(f"[{key}]", "")
            warnings.append(f"Citation supprimée : [{key}] ne vient d'aucun outil.")
    return answer, warnings


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description="Agent Haqqi avec outils MCP")
    parser.add_argument("question")
    args = parser.parse_args(argv)
    out = asyncio.run(run(args.question))
    print("Outils appelés par le LLM :")
    for name, a in out["tool_calls"]:
        print(f"  • {name}({a})")
    print("\nRéponse :\n" + str(out["answer"]))
    for w in out["warnings"]:
        print(f"⚠ {w}")


if __name__ == "__main__":
    main()