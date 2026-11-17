"""Tests de l'étape 3 : aiguillage, graphe LangGraph, vérification des citations.

Le LLM est remplacé par un faux modèle qui renvoie une réponse écrite à l'avance :
on teste le comportement de l'agent sans clé API ni réseau.
"""

import pytest
from langchain_core.language_models.fake_chat_models import FakeMessagesListChatModel
from langchain_core.messages import AIMessage

from haqqi.agent.graph import (HaqqiAgent, asks_about_versions, expand_abbreviations,
                               find_article_reference, label_for)
from haqqi.retrieval.embeddings import HashEmbedder, VectorIndex
from haqqi.retrieval.hybrid import Retriever
from haqqi.retrieval.store import ArticleStore


def rec(doc_id, key, lang, text, current=True, version="v", replaced_by=None):
    return {"id": f"{doc_id}/{key}", "doc_id": doc_id, "article_key": key, "code": key.split(":")[0],
            "lang": lang, "version": version, "text": text, "section": "", "is_current": current,
            "replaced_by": replaced_by, "page": 1, "hash": str(abs(hash(text)) % 10**8), "date": ""}


@pytest.fixture
def retriever():
    store = ArticleStore([
        rec("ct_fr", "ct:53", "fr", "Les enfants de moins de 16 ans ne peuvent être employés."),
        rec("ct_ar", "ct:53", "ar", "لا يمكن تشغيل الأطفال الذين يقل سنهم عن ستة عشر عاما."),
        rec("ct_fr", "ct:112", "fr", "Tout travailleur a droit à un congé annuel payé."),
        rec("ct_fr", "ct:6-4", "fr", "Le contrat à durée déterminée peut être conclu dans les cas suivants.",
            current=False, version="revision_1996", replaced_by="loi_2025_9"),
        rec("loi_ar", "ct:6-4", "ar", "يمنع إبرام عقد شغل لمدة معينة إلا في الحالات الاستثنائية.",
            version="loi_2025_9"),
        rec("c138_en", "c138:2", "en", "Each Member shall specify a minimum age for admission to employment."),
    ])
    index, _ = VectorIndex.build(store.records, HashEmbedder(), cache=None)
    return Retriever(store, index)


def fake_llm(text):
    return FakeMessagesListChatModel(responses=[AIMessage(content=text)])


# --- Aiguillage -----------------------------------------------------------------------------
def test_find_article_reference():
    assert find_article_reference("Que dit l'article 6-4 ?") == "ct:6-4"
    assert find_article_reference("Que dit l'art. 14 bis ?") == "ct:14bis"
    assert find_article_reference("ماذا ينص الفصل 53 ؟") == "ct:53"
    assert find_article_reference("What does Article 2 of the Convention say?") == "c138:2"
    assert find_article_reference("Combien de jours de congé ?") is None


def test_asks_about_versions():
    assert asks_about_versions("Qu'est-ce qui a changé avec la réforme de 2025 ?")
    assert asks_about_versions("ما الذي تغير في الفصل 6-4 ؟")
    assert asks_about_versions("What was amended in article 6-4?")
    assert not asks_about_versions("Après la période d'essai, que se passe-t-il ?")
    assert "durée déterminée" in expand_abbreviations("Un CDD en 2025 ?")


# --- Les trois chemins du graphe (sans LLM) -----------------------------------------------------
def test_lookup_route_reads_the_cited_article(retriever):
    out = HaqqiAgent(retriever, llm=None).ask("Que dit l'article 6-4 ?")
    assert out["route"] == "lookup"
    assert [c["article_key"] for c in out["citations"]] == ["ct:6-4"]
    assert out["citations"][0]["is_current"] and out["citations"][0]["lang"] == "ar"
    assert "(texte original en arabe)" in out["answer"]


def test_compare_route_shows_old_and_current_versions(retriever):
    out = HaqqiAgent(retriever, llm=None).ask("Qu'est-ce qui a changé dans l'article 6-4 avec la réforme ?")
    assert out["route"] == "compare"
    assert "remplacée" in out["answer"] and "en vigueur" in out["answer"]


def test_search_route_answers_in_question_language(retriever):
    out = HaqqiAgent(retriever, llm=None).ask("ما هي السن الدنيا لتشغيل الأطفال؟")
    assert out["language"] == "ar" and out["route"] == "search"
    assert out["answer"].startswith("حسب")
    assert out["citations"][0]["article_key"] == "ct:53"


def test_unknown_article_falls_back_to_search(retriever):
    out = HaqqiAgent(retriever, llm=None).ask("Que dit l'article 999 sur le congé annuel ?")
    assert out["route"] == "search"


# --- Avec un LLM (faux) ------------------------------------------------------------------------------
def test_invalid_citations_are_removed(retriever):
    llm = fake_llm("Les enfants de moins de 16 ans ne peuvent pas travailler [ct:53] [ct:999].")
    out = HaqqiAgent(retriever, llm=llm).ask("Les enfants de moins de 16 ans peuvent-ils être employés ?")
    assert "[ct:999]" not in out["answer"]
    assert out["answer"].endswith("[ct:53].")                # pas d'espace laissé par la suppression
    assert [c["article_key"] for c in out["citations"]] == ["ct:53"]
    assert out["citations"][0]["lang"] == "fr"            # même langue que la question si possible
    assert any("ct:999" in w for w in out["warnings"])


def test_answer_without_citation_means_not_found(retriever):
    out = HaqqiAgent(retriever, llm=fake_llm("Les articles fournis ne parlent pas du télétravail.")).ask(
        "Le télétravail est-il prévu ?")
    assert out["citations"] == []


def test_llm_failure_falls_back_to_extractive(retriever):
    class BrokenLLM:
        def invoke(self, messages):
            raise TimeoutError("quota")
    out = HaqqiAgent(retriever, llm=BrokenLLM()).ask("Que dit l'article 53 ?")
    assert out["citations"] and any("LLM indisponible" in w for w in out["warnings"])


def test_label_in_answer_language():
    r = {"article_key": "c138:2"}
    assert label_for(r, "en") == "ILO Convention No. 138, art. 2"
    assert label_for({"article_key": "ct:6-4"}, "ar") == "مجلة الشغل، الفصل 6-4"