"""Extraction du texte page par page (PDF ou TXT).

Problèmes réels rencontrés dans les PDF arabes (Code du travail 2004, JORT 2025) :

    1. Un mot coupé en deux lignes :   « الف » ⏎ « صل 4 »   au lieu de « الفصل 4 »
       → les morceaux ("spans") à la même hauteur sont recollés sur UNE ligne,
         dans l'ordre où le PDF les stocke (ordre logique de lecture).
    2. Des segments inversés dans un morceau, séparés par un caractère privé (U+E825) :
       « نة␣ة غير معي␣يعتبر … لمد »  au lieu de « يعتبر … لمدة غير معينة »
       → on découpe sur ce caractère et on inverse l'ordre des segments.

On ne trie PAS les morceaux par position horizontale : en arabe, un numéro
comme « 6-2 » s'afficherait alors à l'envers (« 2-6 »).
"""

from __future__ import annotations

import logging
import re
from collections import Counter
from pathlib import Path

from .text_utils import clean_text

log = logging.getLogger(__name__)

Page = tuple[int, str]  # (numéro de page à partir de 1, texte nettoyé)

# Lignes de numéro de page : « 12 », « - 12 - », « Page 12 », « صفحة 12 »
_PAGE_NUMBER = re.compile(r"^(?:[-–—]?\s*\d{1,4}\s*[-–—]?|page\s+\d+|صفحة\s+\d+)$", re.IGNORECASE)

# En-têtes connus des sources utilisées (en plus de la détection automatique)
_KNOWN_HEADERS = [
    re.compile(r"الرائد الر\s*سمي للجمهورية التونسية"),     # Journal officiel (JORT)
    re.compile(r"دعم حقوق المرأة والطفل"),                   # bandeau du site CAWTAR
]

# Trait de séparation des notes de bas de page : « ـــــــــــ » ou « ________ »
_FOOTNOTE_RULE = re.compile(r"^[ـ_\-–—]{8,}$")
# Trait court (« ــ ») suivi d'une note numérotée : « 1 ( الأعمال التحضيرية … »
_SHORT_RULE = re.compile(r"^[ـ_]{2,}$")
_FOOTNOTE_START = re.compile(r"^\s*[()]?\s*\d{1,2}\s*[()]")
# Arabe : lettres qui ne peuvent être qu'en fin de mot, lettres qui ouvrent un mot
_AR_WORD_END = ("ة", "ى", "\ufe94", "\ufe93", "\ufef0", "\ufeef")   # + formes « de présentation » du PDF
_AR_WORD_START = ("إ", "\ufe87", "\ufe88")                            # + formes « de présentation » du PDF

# Caractères de la zone privée Unicode : utilisés par certains PDF comme séparateurs
_PRIVATE_USE = re.compile(r"[\ue000-\uf8ff]")


def extract_pages(path: str | Path, lang: str = "fr") -> list[Page]:
    """Lit un .pdf ou un .txt et retourne la liste des pages nettoyées."""
    path = Path(path)
    if path.suffix.lower() == ".txt":
        raw_pages = path.read_text(encoding="utf-8").split("\f")  # \f = saut de page
    elif path.suffix.lower() == ".pdf":
        raw_pages = _read_pdf(path, rtl=(lang == "ar"))
    else:
        raise ValueError(f"Format non supporté : {path.suffix}")

    pages = [(i + 1, clean_text(t)) for i, t in enumerate(raw_pages)]
    pages = [(n, _drop_footnotes(t)) for n, t in pages]
    pages = _remove_headers_footers(pages)
    _warn_if_scanned(path, pages)
    return pages


# --- Lecture PDF avec reconstruction des lignes -------------------------------------
def _read_pdf(path: Path, rtl: bool) -> list[str]:
    import pymupdf  # import ici : les .txt n'en ont pas besoin

    with pymupdf.open(path) as doc:
        return ["\n".join(_page_lines(page, rtl)) for page in doc]


def _page_lines(page, rtl: bool) -> list[str]:
    """Reconstruit les lignes visuelles d'une page (voir l'en-tête du module)."""
    rows: list[list[dict]] = []
    for block in page.get_text("dict")["blocks"]:
        if block.get("type") != 0:          # 0 = texte (les images sont ignorées)
            continue
        for line in block["lines"]:
            for s in line["spans"]:
                if not s["text"].strip():
                    continue
                x0, y0, x1, y1 = s["bbox"]
                span = {"x0": x0, "x1": x1, "cy": (y0 + y1) / 2, "h": y1 - y0,
                        "text": _fix_private_use(s["text"], rtl)}
                # Même hauteur que la ligne en cours → même ligne visuelle
                if rows:
                    ref = rows[-1][-1]
                    if abs(span["cy"] - ref["cy"]) <= max(2.0, 0.4 * min(span["h"], ref["h"])):
                        rows[-1].append(span)
                        continue
                rows.append([span])

    lines = []
    for row in rows:
        text, prev = "", None
        for s in row:
            if prev is not None and not text.endswith(" ") and not s["text"].startswith(" "):
                gap = max(prev["x0"] - s["x1"], s["x0"] - prev["x1"])
                # Certains PDF n'encodent pas les espaces entre morceaux (écart ≈ 0).
                # En arabe, « ة/ى » finissent forcément un mot et « إ » en commence un.
                word_break = rtl and (text.rstrip().endswith(_AR_WORD_END) or s["text"].startswith(_AR_WORD_START))
                if gap > 1.5 or word_break:
                    text += " "
            text += s["text"]
            prev = s
        lines.append(text)
    return lines


def _fix_private_use(text: str, rtl: bool) -> str:
    """« نة␣ة غير معي␣يعتبر … لمد » → « يعتبر … لمدة غير معينة » (segments inversés)."""
    if not _PRIVATE_USE.search(text):
        return text
    parts = _PRIVATE_USE.split(text)
    return "".join(reversed(parts)) if rtl else "".join(parts)


# --- Nettoyage par page --------------------------------------------------------------
def _drop_footnotes(text: str) -> str:
    """Coupe la page au trait « ـــــــ » : ce qui suit est une note de bas de page."""
    lines = text.splitlines()
    for i, line in enumerate(lines):
        compact = line.replace(" ", "")
        nxt = lines[i + 1] if i + 1 < len(lines) else ""
        if _FOOTNOTE_RULE.match(compact) or (_SHORT_RULE.match(compact) and _FOOTNOTE_START.match(nxt)):
            return "\n".join(lines[:i])
    return text


def _remove_headers_footers(pages: list[Page], min_ratio: float = 0.3) -> list[Page]:
    """Supprime les numéros de page, les en-têtes connus et les lignes répétées sur
    beaucoup de pages (en-têtes / pieds de page)."""
    counts: Counter[str] = Counter()
    for _, text in pages:
        counts.update({line for line in text.splitlines() if line})

    repeated = set()
    if len(pages) >= 5:
        repeated = {line for line, n in counts.items() if n / len(pages) >= min_ratio and len(line) < 60}

    cleaned = []
    for num, text in pages:
        lines = [
            line for line in text.splitlines()
            if line not in repeated
            and not _PAGE_NUMBER.match(line)
            and not any(p.search(line) for p in _KNOWN_HEADERS)
        ]
        cleaned.append((num, "\n".join(lines)))
    return cleaned


def _warn_if_scanned(path: Path, pages: list[Page]) -> None:
    """Un PDF scanné (image) donne presque pas de texte → il faudra un OCR."""
    total = sum(len(t) for _, t in pages)
    if pages and total / len(pages) < 50:
        log.warning(
            "%s : très peu de texte (%d caractères pour %d pages). "
            "PDF probablement scanné → OCR nécessaire (ex. Tesseract avec la langue 'ara').",
            path.name, total, len(pages),
        )