"""Test de l'étape 5 : l'interface Streamlit, lancée sans navigateur (AppTest)."""

import pytest

from haqqi import config

pytestmark = pytest.mark.skipif(not config.ARTICLES_FILE.exists(),
                                reason="lancer d'abord : python -m haqqi.ingestion.pipeline")
APP = str(config.ROOT_DIR / "src" / "haqqi" / "ui" / "app.py")


@pytest.fixture
def app(tmp_path, monkeypatch):
    from streamlit.testing.v1 import AppTest
    from haqqi import service
    monkeypatch.setattr(config, "EMBEDDER", "hash")
    monkeypatch.setattr(config, "LLM_PROVIDER", "none")
    monkeypatch.setattr(config, "VECTORS_FILE", tmp_path / "vectors.npz")
    service.get_agent.cache_clear()
    at = AppTest.from_file(APP, default_timeout=60)
    at.run()
    yield at
    service.get_agent.cache_clear()


def test_page_loads_with_corpus_stats(app):
    assert not app.exception
    sidebar_text = " ".join(m.value for m in app.sidebar.markdown)
    assert "fiches" in sidebar_text and "anglais" in sidebar_text


def test_arabic_question_is_answered_right_to_left_with_sources(app):
    app.chat_input[0].set_value("هل يمكن تشغيل الأطفال الذين يقل سنهم عن ستة عشر عاما؟").run()
    assert not app.exception
    html = " ".join(m.value for m in app.markdown)
    assert 'class="hq-rtl"' in html                        # réponse affichée de droite à gauche
    assert any("[ct:" in e.label for e in app.expander)    # au moins une source citée