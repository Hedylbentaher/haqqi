"""Le serveur MCP de Haqqi (5 outils).

Lancement (le client le fait tout seul) :
    python -m haqqi.mcp_server.server

Les 3 premiers outils sont ceux demandés pour le projet 6 dans l'énoncé.
"""

from __future__ import annotations

from mcp.server.fastmcp import FastMCP

from .. import service

mcp = FastMCP("haqqi", log_level="WARNING")


@mcp.tool()
def search_by_language(query: str, doc_language: str = "", k: int = 5,
                       include_old_versions: bool = False) -> list[dict]:
    """Cherche les articles de loi les plus pertinents pour une question, dans n'importe quelle langue.

    query: la question ou les mots-clés (arabe, français ou anglais).
    doc_language: langue des documents à fouiller : "ar", "fr", "en", ou "" pour toutes.
    k: nombre d'articles à renvoyer.
    include_old_versions: true pour inclure les versions remplacées (avant la loi 2025-9).
    """
    return service.search_by_language(query, doc_language, k, include_old_versions)


@mcp.tool()
def answer_with_citations(question: str) -> dict:
    """Répond à une question sur le droit du travail tunisien, dans la langue de la question,
    en citant les articles utilisés (clé, langue, version, page)."""
    return service.answer_with_citations(question)


@mcp.tool()
def ingest_document(path: str, doc_id: str, lang: str, title: str, kind: str = "code", code: str = "",
                    version: str = "v1", date: str = "", target_code: str = "ct") -> dict:
    """Ajoute ou met à jour un document (PDF ou TXT) dans le corpus, puis met l'index à jour.

    lang: "ar", "fr" ou "en". kind: "code", "amending_law" (loi qui modifie un code) ou "convention".
    Seuls les articles nouveaux ou modifiés sont recalculés.
    """
    return service.ingest_document(path, doc_id, lang, title, kind, code, version, date, target_code)


@mcp.tool()
def get_article(article_key: str, lang: str = "") -> list[dict]:
    """Lit un article précis dans toutes ses langues et versions. Exemples de clés : ct:53, ct:6-4, c138:2."""
    return service.get_article(article_key, lang)


@mcp.tool()
def compare_versions(article_key: str) -> list[dict]:
    """Compare les versions d'un article : texte d'avant et texte en vigueur (ex. ct:6-4 et la loi 2025-9)."""
    return service.compare_versions(article_key)


if __name__ == "__main__":
    mcp.run()   # transport stdio