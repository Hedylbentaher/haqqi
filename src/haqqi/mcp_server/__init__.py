"""Étape 4 — Serveur MCP : les outils de Haqqi, utilisables par n'importe quel client MCP.

    client MCP (script, agent LangGraph, Claude Desktop…)
        │  protocole MCP (stdio)
        ▼
    serveur « haqqi » ── ingest_document · search_by_language · answer_with_citations
                         get_article · compare_versions
"""