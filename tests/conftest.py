"""Textes d'exemple FICTIFS utilisés par les tests.

Ils imitent la mise en forme des vrais textes (titres d'articles, sections,
ordre inversé de certains PDF arabes) mais leur contenu juridique est inventé.
"""

import pytest

CODE_FR = """\
Loi n° 66-27 du 30 avril 1966, portant promulgation du code du travail.
Article premier. - Les textes publiés ci-après forment le code du travail.
Article 2. - Disposition transitoire d'exemple.
CODE DU TRAVAIL
LIVRE PREMIER
DISPOSITIONS GÉNÉRALES
TITRE PREMIER - Du contrat de travail
Article premier. - Le présent code s'applique aux établissements d'exemple.
Article 2. - Texte d'exemple de l'article deux, qui renvoie aux sanctions prévues à
Article 234 du présent code, pour vérifier qu'une référence n'est pas un titre.
Section des dispositions particulières applicables aux exemples
Article 6-4. - Ancienne version d'exemple de l'article 6-4.
Article 30 : Ancienne version d'exemple de l'article 30.
TITRE II
DES SANCTIONS
Article 234 bis - Texte d'exemple de l'article 234 bis.
"""

LOI_FR = """\
Loi n° 2025-9 relative à l'organisation des contrats de travail (exemple).
Article premier - Les dispositions des articles 6-4 et 30 du code du travail
sont abrogées et remplacées par ce qui suit :
Article 6-4 (nouveau) - Nouvelle version d'exemple de l'article 6-4.
Article 30 (nouveau) : Nouvelle version d'exemple de l'article 30.
Article 2 - Disposition transitoire d'exemple de la loi.
"""

# Imite un PDF arabe mal extrait : « 1الفصل » (numéro avant le mot), loi de
# promulgation avec ses propres articles 1 à 2, puis le code qui recommence à 1.
CODE_AR = """\
قانون عدد 27 لسنة 1966 يتعلق بإصدار مجلة الشغل
1الفصل
النصوص المنشورة في ما يلي تؤلف مجلة الشغل (مثال).
2الفصل
حكم انتقالي (مثال).
مجلة الشغل
الكتاب الأول
أحكام عامة
العنوان الأول ـ عقد الشغل
الفصل الأول ـ تنطبق أحكام هذه المجلة على المؤسسات (مثال).
الفصل 2 ـ نص المثال للفصل الثاني يحيل على العقوبات المنصوص عليها في
الفصل 234 من هذه المجلة.
الفصل 6-4 ـ النسخة القديمة للفصل 6-4 (مثال).
الفصل 234 مكرر ـ نص المثال للفصل 234 مكرر.
"""

LOI_AR = """\
قانون عدد 9 لسنة 2025 (مثال)
الفصل الأول ـ تلغى أحكام الفصل 6-4 من مجلة الشغل وتعوض بما يلي:
الفصل 6-4 (جديد) ـ النسخة الجديدة للفصل 6-4 (مثال).
الفصل 2 ـ حكم انتقالي للقانون (مثال).
"""


def _source(doc_id, lang, kind="code", **kw):
    base = {
        "doc_id": doc_id, "file": doc_id, "lang": lang, "kind": kind,
        "code": "ct", "version": "edition_test", "date": "2004-01-01", "title": doc_id,
    }
    if kind == "amending_law":
        base.update(code="loi_2025_9", target_code="ct", version="loi_2025_9", date="2025-05-23")
    base.update(kw)
    return base


@pytest.fixture
def sources():
    return {
        "ct_fr": _source("ct_fr", "fr"),
        "ct_ar": _source("ct_ar", "ar"),
        "loi_fr": _source("loi_fr", "fr", kind="amending_law"),
        "loi_ar": _source("loi_ar", "ar", kind="amending_law"),
    }


@pytest.fixture
def corpus_dir(tmp_path, sources):
    """Crée un mini-dépôt : data/sources.json + data/raw/*.txt"""
    import json

    raw = tmp_path / "raw"
    raw.mkdir()
    texts = {"ct_fr": CODE_FR, "ct_ar": CODE_AR, "loi_fr": LOI_FR, "loi_ar": LOI_AR}
    for doc_id, text in texts.items():
        (raw / f"{doc_id}.txt").write_text(text, encoding="utf-8")
    (tmp_path / "sources.json").write_text(
        json.dumps({"documents": list(sources.values())}, ensure_ascii=False), encoding="utf-8"
    )
    return tmp_path