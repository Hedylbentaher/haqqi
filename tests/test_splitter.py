from conftest import CODE_AR, CODE_FR, LOI_AR, LOI_FR

from haqqi.ingestion.splitter import (
    canonical_number,
    match_article_heading,
    match_section_heading,
    split_into_articles,
)
from haqqi.ingestion.text_utils import clean_text


def _pages(text):
    return [(1, clean_text(text))]


def _by_key(articles):
    return {a.article_key: a for a in articles}


# --- Numéros ---------------------------------------------------------------------
def test_canonical_number():
    assert canonical_number("6 – 4") == "6-4"
    assert canonical_number("premier") == "1"
    assert canonical_number("الأول") == "1"
    assert canonical_number("234", "bis") == "234bis"
    assert canonical_number("234", "مكرر") == "234bis"  # même clé en AR et FR


# --- Titres d'articles -------------------------------------------------------------
def test_french_headings():
    m = match_article_heading("Article 6-4 (nouveau) - Le contrat…", "fr")
    assert (m.number, m.is_new, m.rest) == ("6-4", True, "Le contrat…")
    assert match_article_heading("Art. 234 bis : sanctions", "fr").number == "234bis"
    m = match_article_heading("Article premier. - Texte", "fr")
    assert (m.number, m.rest) == ("1", "Texte")       # le séparateur « . - » est retiré
    assert match_article_heading("Article 6-4 (nouveau). - Texte", "fr").rest == "Texte"
    assert match_article_heading("Article 14", "fr").number == "14"  # titre seul sur sa ligne


def test_french_reference_is_not_a_heading():
    assert match_article_heading("Article 234 du présent code, pour", "fr") is None
    assert match_article_heading("l'article 6 est abrogé", "fr") is None


def test_arabic_headings():
    m = match_article_heading("الفصل 6-4 (جديد) ـ النص", "ar")
    assert (m.number, m.is_new, m.rest) == ("6-4", True, "النص")
    assert match_article_heading("الفصل الأول ـ نص", "ar").number == "1"
    assert match_article_heading("الفصل 234 مكرر ـ نص", "ar").number == "234bis"


def test_arabic_reversed_heading_from_pdf():
    assert match_article_heading("1 الفصل", "ar").number == "1"
    assert match_article_heading("مكرر 234 الفصل", "ar").number == "234bis"


def test_arabic_reference_is_not_a_heading():
    assert match_article_heading("الفصل 234 من هذه المجلة.", "ar") is None
    assert match_article_heading("فصل العامل عن العمل", "ar") is None


def test_section_headings():
    assert match_section_heading("TITRE II", "fr")[2] is True          # nom absent
    assert match_section_heading("TITRE PREMIER - Du contrat", "fr")[:1] == (1,)
    assert match_section_heading("Section des dispositions particulières", "fr") is None
    assert match_section_heading("الباب الأول", "ar")[0] == 2
    assert match_section_heading("القسم الاستشفائي يعمل", "ar") is None


# --- Découpage complet -------------------------------------------------------------
def test_split_french_code(sources):
    arts = _by_key(split_into_articles(_pages(CODE_FR), sources["ct_fr"]))
    # la loi de promulgation (articles 1-2) est séparée du code lui-même
    assert "ct@partie1:1" in arts and "ct@partie1:2" in arts
    assert {"ct:1", "ct:2", "ct:6-4", "ct:30", "ct:234bis"} <= arts.keys()
    # la référence « Article 234 du présent code » reste dans le texte de l'article 2
    assert "Article 234 du présent code" in arts["ct:2"].text
    assert "ct:234" not in arts
    # hiérarchie
    assert "LIVRE PREMIER — DISPOSITIONS GÉNÉRALES" in arts["ct:1"].section
    assert "TITRE II — DES SANCTIONS" in arts["ct:234bis"].section


def test_split_arabic_code(sources):
    arts = _by_key(split_into_articles(_pages(CODE_AR), sources["ct_ar"]))
    assert {"ct@partie1:1", "ct@partie1:2"} <= arts.keys()          # « 1الفصل » inversé
    assert {"ct:1", "ct:2", "ct:6-4", "ct:234bis"} <= arts.keys()
    assert "الفصل 234 من هذه المجلة" in arts["ct:2"].text
    assert arts["ct:1"].section.startswith("الكتاب الأول — أحكام عامة")


def test_split_amending_law_targets_code_articles(sources):
    fr = _by_key(split_into_articles(_pages(LOI_FR), sources["loi_fr"]))
    assert fr["ct:6-4"].is_new and fr["ct:6-4"].version == "loi_2025_9"
    assert "ct:30" in fr                       # « Article 30 (nouveau) » → code
    assert {"loi_2025_9:1", "loi_2025_9:2"} <= fr.keys()   # articles propres de la loi

    ar = _by_key(split_into_articles(_pages(LOI_AR), sources["loi_ar"]))
    assert ar["ct:6-4"].is_new
    assert {"loi_2025_9:1", "loi_2025_9:2"} <= ar.keys()


def test_same_key_in_arabic_and_french(sources):
    """La même clé ct:6-4 existe en AR et FR → on pourra comparer les deux langues."""
    fr = _by_key(split_into_articles(_pages(CODE_FR), sources["ct_fr"]))
    ar = _by_key(split_into_articles(_pages(CODE_AR), sources["ct_ar"]))
    assert {"ct:6-4", "ct:234bis"} <= fr.keys() & ar.keys()