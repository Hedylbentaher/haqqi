"""Tests de l'étape 4 : le vrai serveur MCP, un vrai client, et un agent qui appelle les outils.

Les tests qui lancent le serveur utilisent les fiches de l'étape 1 (data/processed) :
ils sont ignorés si le pipeline n'a pas encore été lancé.
"""

import asyncio
import json

import pytest
from langchain_core.language_models.fake_chat_models import FakeMessagesListChatModel
from langchain_core.messages import AIMessage

from haqqi import config, service

needs_corpus = pytest.mark.skipif(not config.ARTICLES_FILE.exists(),
                                  reason="lancer d'abord : python -m haqqi.ingestion.pipeline")


@pytest.fixture
def light_env(tmp_path, monkeypatch):
    """Serveur sans téléchargement ni clé API : modèle « hash », pas de LLM, index temporaire."""
    monkeypatch.setenv("HAQQI_EMBEDDER", "hash")
    monkeypatch.setenv("HAQQI_LLM_PROVIDER", "none")
    monkeypatch.setenv("HAQQI_INDEX_DIR", str(tmp_path / "index"))


@needs_corpus
def test_client_lists_and_calls_tools(light_env):
    from haqqi.mcp_server.client import demo
    out = asyncio.run(demo("Les enfants de moins de 16 ans peuvent-ils être employés ?"))
    assert {"search_by_language", "answer_with_citations", "ingest_document",
            "get_article", "compare_versions"} == set(out["tools"])
    assert out["answer"]["citations"], "la réponse doit citer au moins un article"


class ToolCallingFake(FakeMessagesListChatModel):
    """Faux LLM qui « décide » d'appeler un outil, puis répond."""

    def bind_tools(self, tools, **kwargs):
        return self


@needs_corpus
def test_llm_agent_calls_mcp_tools(light_env):
    from haqqi.mcp_server.agent_mcp import run
    llm = ToolCallingFake(responses=[
        AIMessage(content="", tool_calls=[{"name": "get_article", "args": {"article_key": "ct:53", "lang": "fr"},
                                           "id": "call_1", "type": "tool_call"}]),
        AIMessage(content="Les enfants de moins de 16 ans ne peuvent pas être employés [ct:53] [ct:999]."),
    ])
    out = asyncio.run(run("Que dit l'article 53 ?", llm=llm))
    assert out["tool_calls"] == [("get_article", {"article_key": "ct:53", "lang": "fr"})]
    tool_messages = [m for m in out["messages"] if m.type == "tool"]
    assert "16 ans" in str(tool_messages[0].content)          # le serveur MCP a bien renvoyé l'article
    assert "[ct:53]" in out["answer"]
    assert "[ct:999]" not in out["answer"] and any("ct:999" in w for w in out["warnings"])   # citation inventée


def test_ingest_document_adds_then_detects_no_change(tmp_path, monkeypatch):
    raw, proc = tmp_path / "raw", tmp_path / "processed"
    raw.mkdir()
    (tmp_path / "sources.json").write_text(json.dumps({"documents": []}), encoding="utf-8")
    for name, value in {"RAW_DIR": raw, "SOURCES_FILE": tmp_path / "sources.json",
                        "ARTICLES_FILE": proc / "articles.jsonl", "MANIFEST_FILE": proc / "manifest.json",
                        "VECTORS_FILE": tmp_path / "index" / "vectors.npz", "EMBEDDER": "hash",
                        "LLM_PROVIDER": "none"}.items():
        monkeypatch.setattr(config, name, value)
    service.get_agent.cache_clear()
    doc = tmp_path / "convention.txt"
    doc.write_text("Preamble\nArticle 1\nEach Member shall pursue a national policy.\n"
                   "Article 2\nNo one under fifteen years shall be admitted to employment.\n", encoding="utf-8")

    first = service.ingest_document(str(doc), "c999_en", "en", "Test convention", kind="convention", code="c999")
    assert (first["status"], first["articles"], first["vectors_computed"]) == ("ingested", 2, 2)

    again = service.ingest_document(str(doc), "c999_en", "en", "Test convention", kind="convention", code="c999")
    assert again["status"] == "unchanged" and again["vectors_computed"] == 0

    hits = service.search_by_language("under fifteen years employment", doc_language="en")
    assert hits[0]["article_key"] == "c999:2"
    service.get_agent.cache_clear()