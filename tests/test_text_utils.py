from haqqi.ingestion.text_utils import (
    clean_text,
    detect_language,
    normalize_arabic,
    normalize_for_search,
)


def test_arabic_indic_digits_become_western():
    assert clean_text("الفصل ٢٣٤") == "الفصل 234"


def test_number_glued_to_arabic_word_is_separated():
    assert clean_text("27قانون") == "27 قانون"
    assert clean_text("1الفصل") == "1 الفصل"


def test_presentation_forms_are_converted():
    # U+FEFB (forme de présentation de « لا ») → « لا »
    assert clean_text("\ufefb") == "لا"


def test_invisible_marks_removed():
    assert clean_text("الفصل\u200f 6") == "الفصل 6"


def test_french_hyphenation_rejoined():
    assert clean_text("les travail-\nleurs") == "les travailleurs"


def test_normalize_arabic_removes_vowels_and_unifies_letters():
    assert normalize_arabic("الأَجْرُ") == normalize_arabic("الاجر")
    assert normalize_arabic("مدّة") == normalize_arabic("مده")


def test_normalize_for_search_latin():
    assert normalize_for_search("Congé payé, l'employeur.") == "conge paye l employeur"


def test_detect_language():
    assert detect_language("ما هي مدة العطلة السنوية؟") == "ar"
    assert detect_language("Quelle est la durée du congé annuel ?") == "fr"
    assert detect_language("How many days of annual leave does a worker get?") == "en"