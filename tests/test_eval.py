"""Tests de l'étape 6 : mesures Recall@k, MRR, faits attendus, et questions d'évaluation."""

import json

import pytest

from haqqi import config
from haqqi.eval.metrics import facts_found, recall_at_k, reciprocal_rank


def test_recall_and_mrr_on_the_documented_example():
    ranked, gold = ["ct:54", "ct:53", "c138:7", "c138:2"], ["ct:53", "c138:2"]
    assert recall_at_k(ranked, gold, 1) == 0
    assert recall_at_k(ranked, gold, 3) == 0.5
    assert recall_at_k(ranked, gold, 5) == 1.0
    assert reciprocal_rank(ranked, gold) == 0.5
    assert reciprocal_rank(["ct:1"], gold) == 0.0


def test_facts_accept_any_spelling_and_digit_groups():
    assert facts_found("L'amende est de 10 000 dinars.", [["10000", "dix mille"]])
    assert facts_found("الخطية عشرة آلاف دينار", [["10000", "عشرة آلاف"]])
    assert facts_found("Six months, renewable once.", [["6", "ستة", "six"]])
    assert not facts_found("Quinze jours.", [["30", "trente"]])
    assert facts_found("Réponse sans fait attendu.", [])


def test_questions_file_is_valid():
    qs = [json.loads(l) for l in config.QUESTIONS_FILE.read_text(encoding="utf-8").splitlines() if l.strip()]
    assert len(qs) >= 50                                       # exigence du cours
    assert {q["lang"] for q in qs} == {"ar", "fr", "en"}
    assert len({q["id"] for q in qs}) == len(qs)
    for q in qs:
        assert (q["type"] == "out_of_scope") == (q["gold"] == [])


@pytest.mark.skipif(not config.ARTICLES_FILE.exists(), reason="lancer d'abord le pipeline")
def test_every_gold_article_exists_in_the_corpus():
    keys = {json.loads(l)["article_key"] for l in config.ARTICLES_FILE.read_text(encoding="utf-8").splitlines()}
    qs = [json.loads(l) for l in config.QUESTIONS_FILE.read_text(encoding="utf-8").splitlines() if l.strip()]
    assert {g for q in qs for g in q["gold"]} <= keys