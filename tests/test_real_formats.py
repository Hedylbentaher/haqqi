"""Cas réels rencontrés dans les PDF du Code du travail (2004) et de la loi 2025-9 (JORT).

Chaque test reprend une ligne telle qu'elle sort de l'extraction, pour éviter
qu'une modification future casse un cas déjà résolu.
"""

from haqqi.ingestion.pdf_extract import _drop_footnotes, _fix_private_use
from haqqi.ingestion.pipeline import mark_current_versions
from haqqi.ingestion.splitter import (
    match_article_heading,
    match_range_heading,
    parse_amendment,
    split_into_articles,
)
from haqqi.ingestion.text_utils import clean_text


# --- Nettoyage -----------------------------------------------------------------------
def test_kashida_inside_words_removed():
    assert clean_text("لا يكون سببـــا لفســـخ العقـــد") == "لا يكون سببا لفسخ العقد"


def test_dash_tatweel_between_spaces_kept():
    assert clean_text("محل ـ المفلس ـ في") == "محل ـ المفلس ـ في"


def test_space_before_shadda_removed():
    assert clean_text("نق \u0651ح بالقانون") == "نقّح بالقانون"


def test_private_use_segments_reversed():
    raw = "نة\ue825ة غير معي\ue825يعتبر عقد الشغل مبرما لمد"
    assert _fix_private_use(raw, rtl=True) == "يعتبر عقد الشغل مبرما لمدة غير معينة"


def test_short_footnote_rule_cuts_page():
    page = "نص المادة.\nــ\n1 ( الأعمال التحضيرية:\nمداولة مجلس نواب الشعب"
    assert _drop_footnotes(page) == "نص المادة."


# --- Titres d'articles -------------------------------------------------------------------
def test_jort_colon_inside_parenthesis():
    m = match_article_heading("الفصل 28) جديد: (تمنع مناولة اليد العاملة.", "ar")
    assert (m.number, m.is_new, m.rest) == ("28", True, "تمنع مناولة اليد العاملة.")


def test_sentence_ending_reference_is_not_heading():
    assert match_article_heading("الفصل 359.", "ar") is None


def test_shadda_in_suffix():
    m = match_article_heading("الفصل 14 مكرّر)أضيف بالقانون عدد 29 لسنة 1994 المؤرخ في 21 فيفري 1994(.", "ar")
    assert m.number == "14bis"
    assert parse_amendment(m.note) == "ajouté"


def test_tatweel_sub_article():
    assert match_article_heading("الفصل 151 ـ2) أضيف بالقانون عدد 62 لسنة 1996(.", "ar").number == "151-2"


def test_paragraph_replacement():
    m = match_article_heading("الفصل 94-2 الفقرة الأولى)جديدة(: يمكن إبرام عقد الشغل", "ar")
    assert (m.number, m.is_new, m.paragraph) == ("94-2", True, "الفقرة الأولى")


def test_range_of_abrogated_articles():
    numbers, note = match_range_heading("الفصول 325 إلى 332) ألغيت بالقانون عدد 62 لسنة 1996(.")
    assert numbers == [str(n) for n in range(325, 333)]
    assert parse_amendment(note) == "abrogé"
    assert match_range_heading("الفصلان 336 و 337) ألغيا بالقانون عدد 62 لسنة 1996.(")[0] == ["336", "337"]
    assert match_range_heading(")ألغيت الفصول 391 إلى 396 بالقانون عدد 62 لسنة 1996.(")[0][0] == "391"


# --- Découpage ------------------------------------------------------------------------------
SRC_CODE = {"doc_id": "ct_ar", "lang": "ar", "kind": "code", "code": "ct", "version": "edition_2004", "date": "2004-01-01"}
SRC_LAW = {"doc_id": "loi_ar", "lang": "ar", "kind": "amending_law", "code": "loi_2025_9",
           "target_code": "ct", "version": "loi_2025_9", "date": "2025-05-21"}


def _split(text, src):
    return {a.article_key: a for a in split_into_articles([(1, clean_text(text))], src)}


def test_heading_note_on_two_lines_is_merged():
    text = (
        "الفصل 236) نقّح بالقانون عدد 16 لسنة 1969 المؤرخ في 27 مارس 1969 ثمّ بالقانون عدد 29 لسنة\n"
        "1994 المؤرخ في 21 فيفري 1994(.\n"
        "يعاقب بنفس الخطية.\n"
        "الفصل 237\nنص الفصل.\n"
    )
    arts = _split(text, SRC_CODE)
    assert arts["ct:236"].text == "يعاقب بنفس الخطية."
    assert arts["ct:236"].extra["status"] == "modifié"
    assert "1994" in arts["ct:236"].extra["amendment"]


def test_damaged_law_heading_accepted_by_sequence():
    text = "الفصل 7 ـ نص الفصل السابع.\nالفصل 8 ي الأجراء المستخدمون…\nالفصل 9 ـ نص."
    arts = _split(text, SRC_LAW)
    assert {"loi_2025_9:7", "loi_2025_9:8", "loi_2025_9:9"} <= arts.keys()


def test_abrogated_and_partial_versions():
    records = {
        "a": {"article_key": "ct:9", "lang": "ar", "date": "2004", "doc_id": "ct_ar", "version": "v2004", "status": "abrogé"},
        "b": {"article_key": "ct:94-2", "lang": "ar", "date": "2004", "doc_id": "ct_ar", "version": "v2004"},
        "c": {"article_key": "ct:94-2", "lang": "ar", "date": "2025", "doc_id": "loi_ar", "version": "loi", "paragraph": "الفقرة الأولى"},
    }
    mark_current_versions(records)
    assert records["a"]["is_current"] is False and records["a"]["replaced_by"] == "abrogé"
    # remplacement d'un seul paragraphe : les deux restent en vigueur
    assert records["b"]["is_current"] is True and records["c"]["is_current"] is True


# --- Édition française (codification révisée au 15 juillet 1996) -------------------------
SRC_FR = {"doc_id": "ct_fr", "lang": "fr", "kind": "code", "code": "ct", "version": "revision_1996", "date": "1996-07-15"}


def test_french_heading_variants():
    assert match_article_heading("Art.123 : Les travailleurs ont droit", "fr").number == "123"
    assert match_article_heading("Art 430 - La médaille du Travail", "fr").number == "430"
    assert match_article_heading("Art 14. quater - La faute grave", "fr").number == "14quater"
    assert match_article_heading("Art. 14 quinter - Il appartient au juge", "fr").number == "14quinquies"


def test_french_bracketed_article_is_abrogated():
    m = match_article_heading("[Art. 9 - Les salariés, dont le contrat de travail aura été résilié]", "fr")
    assert m.number == "9" and parse_amendment(m.note) == "abrogé"
    assert not m.rest.endswith("]")


def test_french_heading_without_separator_accepted_by_sequence():
    text = "Art. 167 - Texte.\nArt. 168 Les membres de la commission sont tenus au secret.\nArt. 169 - Texte."
    arts = _split(text, SRC_FR)
    assert {"ct:167", "ct:168", "ct:169"} <= arts.keys()
    # une phrase qui cite un article n'est pas un titre
    arts = _split("Art. 167 - Texte qui renvoie à\nArt. 168 du présent code.\n", SRC_FR)
    assert "ct:168" not in arts


def test_law_in_arabic_replaces_french_text_too():
    records = {
        "fr": {"article_key": "ct:6-4", "lang": "fr", "date": "1996-07-15", "doc_id": "ct_fr", "version": "revision_1996", "source_kind": "code"},
        "ar": {"article_key": "ct:6-4", "lang": "ar", "date": "2004-01-01", "doc_id": "ct_ar", "version": "edition_2004", "source_kind": "code"},
        "loi": {"article_key": "ct:6-4", "lang": "ar", "date": "2025-05-21", "doc_id": "loi_ar", "version": "loi_2025_9", "source_kind": "amending_law"},
    }
    mark_current_versions(records)
    assert records["loi"]["is_current"] is True
    assert records["ar"]["replaced_by"] == "loi_2025_9"
    assert records["fr"]["is_current"] is False and records["fr"]["replaced_lang"] == "ar"


# --- Document anglais : Convention OIT n° 138 (âge minimum) -------------------------------
SRC_EN = {"doc_id": "c138_en", "lang": "en", "kind": "convention", "code": "c138", "version": "oit_1973", "date": "1973-06-26"}


def test_english_convention_articles():
    text = (
        "Preamble\nThe General Conference of the International Labour Organisation,\n"
        "Article 1\nEach Member undertakes to pursue a national policy.\n"
        "Article 2\n1. Each Member shall specify a minimum age, in accordance with\n"
        "Article 102 of the Charter of the United Nations.\n"
    )
    arts = _split(text, SRC_EN)
    assert set(arts) == {"c138:1", "c138:2"}            # le préambule est ignoré
    assert "Article 102 of the Charter" in arts["c138:2"].text   # une référence n'est pas un titre
    assert arts["c138:1"].lang == "en"