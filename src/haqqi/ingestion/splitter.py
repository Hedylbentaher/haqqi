"""Découpage d'un texte de loi en articles (1 article = 1 morceau du RAG).

Pourquoi découper par article et pas par nombre de mots ?
→ Un article est une unité de sens complète, et c'est ce qu'on cite :
  « Code du travail, art. 6-4 ». La bonne réponse du benchmark est aussi un article.

Ce module reconnaît :
- en français : « Article 6-4 (nouveau). - … », « Art. 234 bis : … », « Article premier »
- en arabe    : « الفصل 6-4 (جديد) ـ … », « الفصل 234 مكرر », « الفصل الأول »
- en arabe mal extrait du PDF (ordre inversé) : « 1 الفصل »
- les titres de structure : Livre / Titre / Chapitre / Section, الكتاب / العنوان / الباب / القسم
"""

from __future__ import annotations

import logging
import re
from collections import Counter
from dataclasses import dataclass, field

from .models import Article
from .pdf_extract import Page

log = logging.getLogger(__name__)

# --- Morceaux de regex communs -------------------------------------------------
_NUM = r"\d+(?:\s*[-–ـ]\s*\d+)?"                      # 6   6-4   6 – 4   151 ـ2
_PAREN = r"(?P<paren>\s*[()][^()\n]{1,250}[()])?"     # (nouveau)  )جديد(  (Modifié par…)
# Séparateur(s) « . - », fin de ligne, ou rien si le « : » est déjà dans la parenthèse
# (le PDF du JORT donne « الفصل 28) جديد: (تمنع … » : le « : » est à l'intérieur).
_SEP = r"(?P<sep>(?:\s*[.:\-–—ـ]+)+\s*|\s*$|(?<=:[()])\s*|(?<=:\s[()])\s*)"
_REST = r"(?P<rest>.*)$"
# Remplacement d'un seul paragraphe : « الفصل 94-2 الفقرة الأولى (جديدة) », « Article 94-2, alinéa 1 (nouveau) »
_AR_PARA = r"(?P<para>\s+(?:الفقرة|الفقرتان|الفقرات)\s+[^()\n:]{1,40}?)?"
_FR_PARA = r"(?P<para>\s*,?\s+(?:paragraphe|alinéa)s?\s+[^()\n:]{1,40}?)?"

# « Art. 5 bis », et aussi « Art 14. quater » (point parasite dans l'édition française)
_FR_SUFFIX = r"(?P<suf>\.?\s*(?:bis|ter|quater|quinquies|quinter|sexies|septies))?"


def _ar_word(word: str) -> str:
    """Regex d'un mot arabe qui tolère les voyelles/chadda : « مكرر » trouve aussi « مكرّر »."""
    return "[\u064B-\u0652]*".join(word)


_AR_SUFFIX_WORDS = "|".join(_ar_word(w) for w in ("مكررا", "مكرر", "ثالثا", "رابعا", "خامسا", "سادسا", "سابعا"))
_AR_SUFFIX = rf"(?P<suf>\s*(?:{_AR_SUFFIX_WORDS}))?"
_TASHKEEL_RE = re.compile(r"[\u064B-\u0652]")

# « Article 6 - », « Art. 6 : », « Art.123 : » (sans espace), « Art 430 - » (sans point)
FR_ARTICLE = re.compile(
    rf"^Art(?:icle\s+|\.\s*|\s+)(?P<num>premier|1er|{_NUM}){_FR_SUFFIX}{_FR_PARA}{_PAREN}{_SEP}{_REST}"
)
# Édition française : « les articles abrogés sont placés entre crochets » → « [Art. 9 - … ] »
_ABROGATED_BRACKET = re.compile(r"^\[\s*(?=Art)")
AR_ARTICLE = re.compile(
    rf"^ال?فصل\s*(?P<num>{_NUM}|الأول|الاول){_AR_SUFFIX}{_AR_PARA}{_PAREN}{_SEP}{_REST}"
)
# Ordre inversé produit par certains PDF arabes : « 1 الفصل », « مكرر 234 الفصل »
AR_ARTICLE_REVERSED = re.compile(
    rf"^(?:(?P<suf>{_ar_word('مكررا')}|{_ar_word('مكرر')})\s*)?(?P<num>{_NUM})\s*ال?فصل(?P<para>){_PAREN}{_SEP}{_REST}"
)

# Titres de structure : mot-clé + numéro/ordinal obligatoire (« TITRE II », « الباب الأول »).
# L'ordinal évite de prendre pour un titre une phrase qui commence par « Section des… ».
_FR_LEVELS = {"livre": 0, "titre": 1, "chapitre": 2, "section": 3}
_AR_LEVELS = {"الكتاب": 0, "العنوان": 1, "الباب": 2, "القسم": 3}
_FR_ORD = r"(?:[IVXLC]+|\d+|(?i:premier|première|unique|préliminaire|[a-zé]+ième))"
_AR_ORD = r"(?:\d+|ال(?:أول|اول|ثاني|ثالث|رابع|خامس|سادس|سابع|ثامن|تاسع|عاشر|حادي|تمهيدي)\S*(?:\s+عشر)?)"
FR_SECTION = re.compile(
    rf"^(?P<level>LIVRE|Livre|TITRE|Titre|CHAPITRE|Chapitre|SECTION|Section)\s+(?P<ord>{_FR_ORD})\b(?P<name>.{{0,100}})$"
)
AR_SECTION = re.compile(rf"^(?P<level>الكتاب|العنوان|الباب|القسم)\s+(?P<ord>{_AR_ORD})(?P<name>.{{0,100}})$")

_NEW_MARK = re.compile(r"nouveau|nouvelle|جديد|جديدة", re.IGNORECASE)
_SUFFIX_CANON = {
    "bis": "bis", "مكرر": "bis", "مكررا": "bis",
    "ter": "ter", "ثالثا": "ter",
    "quater": "quater", "رابعا": "quater",
    "quinquies": "quinquies", "quinter": "quinquies", "خامسا": "quinquies",   # « quinter » : coquille de l'édition FR
    "sexies": "sexies", "سادسا": "sexies",
    "septies": "septies", "سابعا": "septies",
}


@dataclass
class HeadingMatch:
    number: str           # numéro canonique : "6-4", "234bis", "1"
    is_new: bool          # article marqué « nouveau » / « جديد »
    rest: str             # texte qui suit le titre sur la même ligne
    raw: str              # ligne d'origine
    note: str = ""        # contenu de la parenthèse : « نقّح بالقانون عدد 62 لسنة 1996 … »
    paragraph: str = ""   # « الفقرة الأولى » si seul un paragraphe est remplacé


# Notes d'historique : « (نقّح بالقانون عدد 62 لسنة 1996 …) », « (Abrogé par la loi n° 96-62 …) »
_AMENDMENT = [
    ("abrogé", re.compile(r"ألغي|ألغيت|أبطل|abrog", re.IGNORECASE)),
    ("ajouté", re.compile(r"أضيف|أضيفت|ajout", re.IGNORECASE)),
    ("modifié", re.compile(r"نقح|نقّح|نقحت|تمم|تمّم|modifi|complét", re.IGNORECASE)),
]
_AMENDMENT_NOTE_AT_START = re.compile(r"^\s*[()]([^()]{5,200})[()]\s*[.:]*\s*")


def parse_amendment(note: str) -> str:
    """« ألغي بالقانون عدد 62 لسنة 1996 » → « abrogé » ; rien trouvé → « »."""
    for status, pattern in _AMENDMENT:
        if pattern.search(note):
            return status
    return ""


def canonical_number(num: str, suffix: str | None = None) -> str:
    """« 6 – 4 » → « 6-4 » ; « premier » / « الأول » → « 1 » ; (« 234 », « مكرر ») → « 234bis »."""
    num = num.strip()
    if num in {"premier", "1er", "الأول", "الاول"}:
        num = "1"
    num = re.sub(r"\s*[-–ـ]\s*", "-", num)
    if suffix:
        suffix = _TASHKEEL_RE.sub("", suffix.strip(" ."))  # « مكرّر » → « مكرر », « . quater » → « quater »
        num += _SUFFIX_CANON.get(suffix, suffix)
    return num


def match_article_heading(line: str, lang: str) -> HeadingMatch | None:
    """Teste si une ligne est un titre d'article. Retourne None sinon.

    Garde-fou contre les faux positifs : après le numéro, il faut un séparateur
    (« . - », « : », « ـ ») ou la fin de la ligne. Ainsi une référence coupée en
    fin de ligne comme « Article 234 du présent code » n'est PAS prise pour un titre.
    """
    patterns = [AR_ARTICLE, AR_ARTICLE_REVERSED] if lang == "ar" else [FR_ARTICLE]
    bracketed = bool(_ABROGATED_BRACKET.match(line))
    if bracketed:
        line = _ABROGATED_BRACKET.sub("", line)
    for pattern in patterns:
        m = pattern.match(line)
        if not m:
            continue
        rest = m.group("rest").strip()
        paren = m.group("paren") or ""
        # Arabe : « الفصل 359. » en début de ligne = fin d'une phrase qui CITE l'article
        # (les vrais titres arabes n'ont pas de point seul).
        if lang == "ar" and not paren and m.group("sep").strip() == "." and not rest:
            return None
        is_new = bool(_NEW_MARK.search(paren))
        # Marque « (nouveau) » placée après le séparateur : « Article 6-4 - (nouveau) … »
        lead = re.match(r"^[()]\s*(nouveau|nouvelle|جديد|جديدة)\s*[()]\s*[.:\-–—ـ]*\s*", rest, re.IGNORECASE)
        if lead:
            is_new = True
            rest = rest[lead.end():]
        note = paren.strip(" ()") if not is_new else ""
        if bracketed:
            note = note or "abrogé (article entre crochets dans l'édition française)"
            rest = rest.rstrip(" ]")
        return HeadingMatch(
            number=canonical_number(m.group("num"), m.group("suf")),
            is_new=is_new,
            rest=rest,
            raw=line,
            note=note,
            paragraph=(m.group("para") or "").strip(" ,"),
        )
    return None


def match_expected_heading(line: str, lang: str, expected: int) -> HeadingMatch | None:
    """Titre sans séparateur, accepté seulement s'il porte le numéro ATTENDU (précédent + 1).

    Exemples réels : « Art. 168 Les membres de la commission… » (édition française),
    « الفصل 8 ي الأجراء… » (PDF abîmé de la loi 2025-9).
    En français, il faut l'abréviation « Art » suivie d'une majuscule : une phrase
    qui cite un article (« l'article 169 du présent code ») ne passe pas.
    """
    if lang == "ar":
        m = re.match(rf"^ال?فصل\s+{expected}\s+(?P<rest>\S.*)$", line)
    else:
        bracketed = bool(_ABROGATED_BRACKET.match(line))
        m = re.match(rf"^\[?\s*Art\.?\s*{expected}\s+(?P<rest>[A-ZÀ-Ý].*)$", line)
        if m and bracketed:
            return HeadingMatch(str(expected), False, m.group("rest").rstrip(" ]"), line,
                                note="abrogé (article entre crochets dans l'édition française)")
    if not m:
        return None
    return HeadingMatch(str(expected), False, m.group("rest").strip(" ـ-:"), line)


def match_section_heading(line: str, lang: str) -> tuple[int, str, bool] | None:
    """Reconnaît « TITRE II - Du contrat de travail » → (niveau 1, texte, nom_absent=False).

    ``nom_absent`` vaut True pour « TITRE II » seul : le nom est alors sur la ligne suivante.
    """
    line = line.strip()
    if line.startswith("[") and line.endswith("]"):      # « [Chapitre III. Immigration …] » (abrogé)
        line = line[1:-1].strip()
    if len(line) > 110 or line.endswith("."):
        return None
    m = (AR_SECTION if lang == "ar" else FR_SECTION).match(line)
    if not m:
        return None
    levels = _AR_LEVELS if lang == "ar" else _FR_LEVELS
    bare = not m.group("name").strip(" .:-–—ـ")
    return levels[m.group("level").lower() if lang != "ar" else m.group("level")], line, bare


# Plusieurs articles d'un coup, en général abrogés :
#   « الفصول 325 إلى 332 (ألغيت بالقانون …) »   « الفصلان 336 و 337 (ألغيا …) »
#   « (ألغيت الفصول 391 إلى 396 بالقانون …) »   « Articles 325 à 332 (Abrogés par …) »
_RANGE_PATTERNS = [
    re.compile(r"^ال?فصول\s+(?P<a>\d+)\s+(?P<op>إلى|الى)\s+(?P<b>\d+)\s*[()](?P<note>[^()]{3,250})[()]"),
    re.compile(r"^ال?فصلان\s+(?P<a>\d+)\s+(?P<op>و)\s*(?P<b>\d+)\s*[()](?P<note>[^()]{3,250})[()]"),
    re.compile(r"^[()]\s*(?P<note>(?:ألغيت|ألغي)\s+ال?فصول\s+(?P<a>\d+)\s+(?P<op>إلى|الى)\s+(?P<b>\d+)[^()]{0,200})[()]"),
    re.compile(r"^Articles\s+(?P<a>\d+)\s+(?P<op>à|et)\s+(?P<b>\d+)\s*\((?P<note>[^()]{3,250})\)", re.IGNORECASE),
]


def match_range_heading(line: str) -> tuple[list[str], str] | None:
    """« الفصول 325 إلى 332 (ألغيت …) » → (['325', …, '332'], 'ألغيت …')."""
    for pattern in _RANGE_PATTERNS:
        m = pattern.match(line)
        if not m or not parse_amendment(m.group("note")):
            continue
        a, b = int(m.group("a")), int(m.group("b"))
        if m.group("op") in {"و", "et"}:
            numbers = [a, b]
        elif 0 < b - a <= 50:
            numbers = list(range(a, b + 1))
        else:
            continue
        return [str(n) for n in numbers], m.group("note").strip()
    return None


_HEADING_START = re.compile(r"^(?:ال?فصل|ال?فصول|ال?فصلان|Art(?:icle|\.))")


def _merge_unclosed_heading(all_lines: list[tuple[int, str]], i: int, line: str) -> tuple[str, int]:
    """« الفصل 236) نقّح بالقانون … لسنة ⏎ 1994 المؤرخ في … 1994( »
    → la parenthèse continue sur la ligne suivante : on recolle (3 lignes max)."""
    extra = 0
    while _HEADING_START.match(line) and _paren_count(line) % 2 == 1 and extra < 3 and i + extra < len(all_lines):
        line = f"{line} {all_lines[i + extra][1]}"
        extra += 1
    return line, extra


def _paren_count(text: str) -> int:
    return text.count("(") + text.count(")")


@dataclass
class _Draft:
    heading: HeadingMatch
    page: int
    section: str
    part: int
    lines: list[str] = field(default_factory=list)


def split_into_articles(pages: list[Page], source: dict) -> list[Article]:
    """Découpe les pages d'un document en articles.

    ``source`` est l'entrée du catalogue data/sources.json (doc_id, lang, kind, code…).
    """
    lang = source["lang"]
    drafts: list[_Draft] = []
    current: _Draft | None = None
    hierarchy: dict[int, str] = {}
    part = 0
    seen_numbers: set[str] = set()
    is_law = source.get("kind") == "amending_law"
    last_number = 0   # dernier numéro de base vu (loi : ses articles propres 1, 2, 3… seulement)
    # Titre sans séparateur accepté s'il porte le numéro attendu : loi modificative,
    # ou code français (« Art. 168 Les membres… »). Pas pour le code arabe : inutile, et
    # une phrase « الفصل 360 من … » en début de ligne serait prise pour un titre.
    use_sequence = is_law or lang != "ar"

    all_lines = [(page_num, line) for page_num, text in pages for line in text.splitlines()]
    i = 0
    while i < len(all_lines):
        page_num, line = all_lines[i]
        i += 1
        if not line:
            if current:
                current.lines.append("")
            continue

        original = line
        line, extra = _merge_unclosed_heading(all_lines, i, line)

        # Groupe d'articles abrogés : on crée une fiche (vide) par article
        group = match_range_heading(line)
        if group:
            i += extra
            numbers, note = group
            section_label = " > ".join(hierarchy[k] for k in sorted(hierarchy))
            for n in numbers:
                seen_numbers.add(n)
                drafts.append(_Draft(HeadingMatch(n, False, "", line, note=note), page_num, section_label, part))
            current = None
            continue

        heading = match_article_heading(line, lang)
        if heading is None and use_sequence:
            heading = match_expected_heading(line, lang, last_number + 1)
        if heading:
            i += extra
            base = re.match(r"\d+", heading.number)
            counts = not is_law or (heading.number.isdigit() and not heading.is_new)
            if base and counts:
                n = int(base.group())
                last_number = n if (not is_law and n == 1) else max(last_number, n)
            # Numérotation qui recommence à 1 → nouvelle "partie" du document
            # (ex. la loi de promulgation 1966 a ses propres articles 1 à 4 avant le code).
            if heading.number == "1" and "1" in seen_numbers:
                part += 1
                seen_numbers.clear()
            seen_numbers.add(heading.number)
            current = _Draft(heading, page_num, " > ".join(hierarchy[k] for k in sorted(hierarchy)), part)
            if heading.rest:
                current.lines.append(heading.rest)
            drafts.append(current)
            continue

        line = original  # pas un titre d'article : on garde la ligne seule
        section = match_section_heading(line, lang)
        if section:
            level, label, bare = section
            # « TITRE II » seul sur sa ligne → le nom est sur la ligne suivante
            if bare and i < len(all_lines):
                nxt = all_lines[i][1]
                if nxt and len(nxt) < 100 and not match_article_heading(nxt, lang):
                    label = f"{label} — {nxt}"
                    i += 1
            hierarchy = {k: v for k, v in hierarchy.items() if k < level}
            hierarchy[level] = label
            continue

        if current:
            current.lines.append(line)
        # Les lignes avant le premier article (préambule, visas) sont ignorées.

    return _finalize(drafts, source)


def _finalize(drafts: list[_Draft], source: dict) -> list[Article]:
    # Partie principale = celle qui contient le plus d'articles (le code lui-même).
    part_sizes = Counter(d.part for d in drafts)
    main_part = part_sizes.most_common(1)[0][0] if part_sizes else 0
    if len(part_sizes) > 1:
        log.info("%s : %d parties détectées %s, partie principale = %d",
                 source["doc_id"], len(part_sizes), dict(part_sizes), main_part)

    articles: list[Article] = []
    used_ids: Counter[str] = Counter()
    for d in drafts:
        text = "\n".join(d.lines).strip()
        text = re.sub(r"\n{3,}", "\n\n", text)
        code, number = _resolve_code(d, source, main_part)

        # Note d'historique : dans la parenthèse du titre, ou en tout début du texte
        note = d.heading.note
        if not note:
            m = _AMENDMENT_NOTE_AT_START.match(text)
            if m and parse_amendment(m.group(1)):
                note, text = m.group(1).strip(), text[m.end():].strip()
        extra = {"source_kind": source.get("kind", "code")}
        if note and parse_amendment(note):
            extra["amendment"] = note
            extra["status"] = parse_amendment(note)
        if d.heading.paragraph:
            extra["paragraph"] = d.heading.paragraph

        # Sécurité : deux articles avec le même numéro dans la même partie → suffixe #2, #3…
        used_ids[f"{code}:{number}"] += 1
        if used_ids[f"{code}:{number}"] > 1:
            log.warning("%s : article %s en double (occurrence %d)",
                        source["doc_id"], number, used_ids[f"{code}:{number}"])
            number = f"{number}#{used_ids[f'{code}:{number}']}"

        articles.append(Article(
            doc_id=source["doc_id"],
            code=code,
            article=number,
            lang=source["lang"],
            version=source["version"],
            date=source.get("date", ""),
            text=text,
            heading=d.heading.raw,
            section=d.section,
            page=d.page,
            source_file=source.get("_path", ""),
            title=source.get("title", ""),
            is_new=d.heading.is_new,
            extra=extra,
        ))
    return articles


def _resolve_code(d: _Draft, source: dict, main_part: int) -> tuple[str, str]:
    """À quel texte appartient l'article ?

    - Document « code » : partie principale → code (ex. "ct") ; autres parties → "ct@partie2"…
    - Document « amending_law » (loi qui modifie un code) :
        * article marqué « (nouveau) » OU numéro composé (6-4) OU suffixe (bis)
          → c'est la NOUVELLE version d'un article du code cible (ex. "ct")
        * sinon → article propre de la loi (ex. "loi_2025_9", dispositions transitoires)
    """
    number = d.heading.number
    if source.get("kind") == "amending_law":
        targets_code = d.heading.is_new or "-" in number or not number.isdigit()
        if targets_code:
            return source["target_code"], number
        return source["code"], number
    if d.part != main_part:
        return f"{source['code']}@partie{d.part + 1}", number
    return source["code"], number