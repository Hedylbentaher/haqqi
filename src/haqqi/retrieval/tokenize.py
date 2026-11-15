"""Découpage en mots pour BM25, en arabe, français et anglais.

    « Les congés payés des salariés »  →  [cong, paye, salari]
    « للعمّال الحق في عطلة »            →  [عمال, الحق, عطل]   (« حق » : trop court, « ال » est gardé)

Trois opérations :
1. normalisation (étape 1) : sans voyelles arabes, sans accents, minuscules ;
2. suppression des mots vides (« le », « في », « the ») ;
3. racinisation légère : on enlève quelques préfixes et suffixes fréquents.
"""

from __future__ import annotations

from ..ingestion.text_utils import normalize_for_search

# Mots vides, déjà normalisés (sans accents, ة→ه, أ→ا…)
STOPWORDS = {
    # français
    "le", "la", "les", "l", "de", "des", "du", "d", "un", "une", "et", "ou", "a", "au", "aux",
    "en", "dans", "par", "pour", "sur", "que", "qui", "ne", "pas", "est", "sont", "ce", "cette",
    "ces", "se", "sa", "son", "ses", "il", "elle", "ils", "elles", "leur", "leurs", "y", "avec",
    "peut", "peuvent", "doit", "doivent", "etre", "tout", "toute", "tous", "toutes", "si",
    "quel", "quelle", "quels", "quelles", "comment", "combien", "est-ce", "quoi", "selon",
    # anglais
    "the", "of", "and", "or", "to", "in", "for", "on", "by", "is", "are", "be", "an", "this",
    "that", "which", "with", "as", "at", "it", "its", "shall", "may", "not", "what", "how",
    "many", "much", "can", "does", "do", "my", "who", "when",
    # arabe
    "في", "من", "علي", "الي", "عن", "ان", "او", "و", "ما", "لا", "التي", "الذي", "الذين", "هذا",
    "هذه", "ذلك", "تلك", "كل", "بعد", "قبل", "مع", "هو", "هي", "كان", "يكون", "به", "بها", "له",
    "لها", "عليه", "عليها", "فيه", "فيها", "منه", "منها", "اذا", "هل", "كم", "ماهي", "متي", "اي",
}

_AR_PREFIXES = ("وال", "بال", "كال", "فال", "لل", "ال")
_AR_SUFFIXES = ("ها", "ات", "ون", "ين", "ان", "يه", "ه", "ي")


def _is_arabic(token: str) -> bool:
    return any("\u0600" <= ch <= "\u06ff" for ch in token)


def stem(token: str) -> str:
    """Racinisation légère : « والعمال » → « عمال », « salariées » → « salari »."""
    if _is_arabic(token):
        for p in _AR_PREFIXES:
            if token.startswith(p) and len(token) - len(p) >= 3:
                token = token[len(p):]
                break
        for s in _AR_SUFFIXES:
            if token.endswith(s) and len(token) - len(s) >= 3:
                return token[: -len(s)]
        return token
    # français / anglais : pluriel puis « e » final → « congé », « congés » → « cong »
    if token.endswith(("s", "x")) and len(token) > 3:
        token = token[:-1]
    if token.endswith("e") and len(token) > 4:
        token = token[:-1]
    return token


def tokenize(text: str) -> list[str]:
    """Texte → liste de racines, pour l'index BM25 et pour les questions."""
    tokens = []
    for tok in normalize_for_search(text).replace("-", " ").split():
        if tok in STOPWORDS or len(tok) < 2 or tok.isdigit():
            continue
        tokens.append(stem(tok))
    return tokens