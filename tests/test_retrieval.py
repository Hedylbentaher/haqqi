"""Tests de l'étape 2 : tokenisation, BM25, vecteurs (avec cache), fusion RRF, filtres."""

import numpy as np
import pytest

from haqqi.retrieval.bm25 import BM25Index
from haqqi.retrieval.embeddings import E5Embedder, HashEmbedder, VectorIndex
from haqqi.retrieval.hybrid import RRF_K, Retriever
from haqqi.retrieval.store import ArticleStore, citation_label
from haqqi.retrieval.tokenize import stem, tokenize


def rec(doc_id, key, lang, text, current=True, version="v", h=None):
    return {"id": f"{doc_id}/{key}", "doc_id": doc_id, "article_key": key, "code": key.split(":")[0],
            "lang": lang, "version": version, "text": text, "section": "", "is_current": current,
            "hash": h or str(abs(hash(text)) % 10**8)}


@pytest.fixture
def store():
    return ArticleStore([
        rec("ct_fr", "ct:53", "fr", "Les enfants de moins de 16 ans ne peuvent être employés."),
        rec("ct_ar", "ct:53", "ar", "لا يمكن تشغيل الأطفال الذين يقل سنهم عن ستة عشر عاما."),
        rec("ct_fr", "ct:112", "fr", "Tout travailleur a droit à un congé annuel payé."),
        rec("ct_fr", "ct:6-4", "fr", "Ancien texte sur le contrat à durée déterminée.", current=False),
        rec("loi_ar", "ct:6-4", "ar", "يمنع إبرام عقد شغل لمدة معينة إلا في الحالات الاستثنائية."),
        rec("c138_en", "c138:2", "en", "Each Member shall specify a minimum age for admission to employment."),
    ])


# --- Tokenisation ------------------------------------------------------------------------
def test_tokenize_removes_stopwords_and_stems():
    assert tokenize("Les congés payés des salariés") == ["cong", "paye", "salari"]
    assert tokenize("congé") == tokenize("congés")            # singulier = pluriel
    assert tokenize("What is the minimum age?") == ["minimum", "age"]


def test_arabic_light_stemming():
    assert stem("والعمال") == "عمال"
    assert stem("العطله") == "عطل"
    assert stem("حق") == "حق"           # trop court : on ne touche pas


# --- BM25 ----------------------------------------------------------------------------------
def test_bm25_prefers_rare_words():
    idx = BM25Index(["congé annuel payé", "congé de maternité", "salaire minimum garanti"])
    scores = idx.scores("congé de maternité")
    assert int(np.argmax(scores)) == 1                     # « maternité » est rare → décisif
    assert idx.scores("grève")[0] == 0                     # mot absent → 0


def test_bm25_length_normalisation():
    idx = BM25Index(["salaire", "salaire " + "autre mot " * 30])
    s = idx.scores("salaire")
    assert s[0] > s[1]                                      # même mot, texte court = plus pertinent


# --- Vecteurs et cache ---------------------------------------------------------------------
def test_vector_cache_reuses_unchanged_articles(tmp_path, store):
    cache = tmp_path / "vectors.npz"
    emb = HashEmbedder()
    _, r1 = VectorIndex.build(store.records, emb, cache)
    assert (r1.embedded, r1.reused) == (6, 0)
    _, r2 = VectorIndex.build(store.records, emb, cache)
    assert (r2.embedded, r2.reused) == (0, 6)
    changed = [dict(r) for r in store.records]
    changed[0]["text"], changed[0]["hash"] = "texte corrigé", "nouveau"
    _, r3 = VectorIndex.build(changed, emb, cache)
    assert (r3.embedded, r3.reused, r3.removed) == (1, 5, 1)


def test_cache_from_another_model_is_recomputed(tmp_path, store):
    cache = tmp_path / "vectors.npz"
    VectorIndex.build(store.records, HashEmbedder(dim=512), cache)
    other = HashEmbedder(dim=256)
    other.name = "autre-modele"
    index, report = VectorIndex.build(store.records, other, cache)
    assert report.embedded == 6 and index.vectors.shape == (6, 256)


def test_e5_uses_query_and_passage_prefixes():
    class FakeModel:
        def encode(self, texts, **kw):
            self.seen = texts
            return np.ones((len(texts), 4))
    m = FakeModel()
    emb = E5Embedder("fake", model=m)
    emb.encode_queries(["âge minimum"])
    assert m.seen == ["query: âge minimum"]
    emb.encode_passages(["texte"])
    assert m.seen == ["passage: texte"]


# --- Recherche hybride ------------------------------------------------------------------------
def make_retriever(store):
    index, _ = VectorIndex.build(store.records, HashEmbedder(), cache=None)
    return Retriever(store, index)


def test_rrf_score_is_sum_of_inverse_ranks(store):
    r = make_retriever(store)
    top = r.search("enfants de moins de 16 ans employés", k=1, mode="hybrid")[0]
    assert top.article_key == "ct:53"
    expected = sum(1 / (RRF_K + rank) for rank in top.ranks.values())
    assert top.score == pytest.approx(expected)
    assert set(top.ranks) == {"bm25", "vector"}


def test_filters_language_versions_and_code(store):
    r = make_retriever(store)
    assert all(h.record["lang"] == "en" for h in r.search("minimum age", mode="hybrid", lang="en"))
    ids = [h.record["id"] for h in r.search("contrat durée déterminée", k=10, mode="hybrid")]
    assert "ct_fr/ct:6-4" not in ids                       # version remplacée exclue par défaut
    ids_all = [h.record["id"] for h in r.search("contrat durée déterminée", k=10, current_only=False)]
    assert "ct_fr/ct:6-4" in ids_all
    assert all(h.record["code"] == "c138" for h in r.search("age", code="c138", mode="vector"))


def test_search_keys_merges_languages(store):
    r = make_retriever(store)
    keys = r.search_keys("enfants 16 ans الأطفال ستة عشر", k=3)
    assert keys[0] == "ct:53" and len(keys) == len(set(keys))


def test_bm25_mode_needs_no_vectors(store):
    r = Retriever(store, None)
    assert r.search("congé annuel", mode="bm25")[0].article_key == "ct:112"
    with pytest.raises(RuntimeError):
        r.search("congé annuel", mode="hybrid")


def test_citation_label():
    assert citation_label({"article_key": "ct:6-4", "version": "loi_2025_9", "lang": "ar"}) == \
        "Code du travail, art. 6-4 (loi_2025_9, ar)"
    assert citation_label({"article_key": "c138:2", "version": "oit_1973", "lang": "en"}).startswith(
        "Convention OIT n° 138, art. 2")