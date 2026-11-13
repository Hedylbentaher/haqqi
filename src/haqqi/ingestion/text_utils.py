"""Nettoyage et normalisation du texte arabe / français / anglais.

Deux niveaux :
1. ``clean_text``  → texte propre, gardé pour l'affichage et les citations.
2. ``normalize_for_search`` → texte "aplati", utilisé seulement pour la recherche
   (on enlève les voyelles arabes, les accents français, etc.).
"""

from __future__ import annotations

import re
import unicodedata

# --- Chiffres -----------------------------------------------------------------
# Chiffres arabes-indiens (٠١٢…) et persans (۰۱۲…) → chiffres occidentaux (012…)
_DIGITS = str.maketrans("٠١٢٣٤٥٦٧٨٩۰۱۲۳۴۵۶۷۸۹", "01234567890123456789")

# --- Caractères invisibles qui gênent la recherche ----------------------------
# zero-width, marques de direction (LRM/RLM), isolats bidi, trait d'union conditionnel
_INVISIBLE = re.compile(r"[\u00ad\u200b-\u200f\u202a-\u202e\u2066-\u2069\ufeff]")

# Lettres arabes (bloc de base)
_AR_LETTER = r"ء-ي"
_AR_LETTER_RE = re.compile(f"[{_AR_LETTER}]")
_LATIN_LETTER_RE = re.compile(r"[A-Za-zÀ-ÖØ-öø-ÿ]")

# Voyelles courtes (tashkeel) + alef suscrit
_TASHKEEL = re.compile(r"[\u064b-\u0652\u0670]")
_TATWEEL = "ـ"


def clean_text(text: str) -> str:
    """Nettoie un texte brut extrait d'un PDF, sans changer son sens.

    - NFKC : convertit les "formes de présentation" arabes (ex. U+FEFB) en lettres normales.
    - Convertit les chiffres arabes-indiens en chiffres occidentaux.
    - Supprime les caractères invisibles.
    - Sépare un nombre collé à un mot arabe (« 27قانون » → « 27 قانون »).
    - Recolle les mots français coupés en fin de ligne (« travail-\\nleurs »).
    - Réduit les espaces multiples.
    """
    text = unicodedata.normalize("NFKC", text)
    text = text.translate(_DIGITS)
    text = _INVISIBLE.sub("", text)
    text = re.sub(r"[\ue000-\uf8ff]", "", text)                       # caractères privés
    text = re.sub(rf"(?<=[{_AR_LETTER}])ـ+(?=[{_AR_LETTER}])", "", text)  # « سببـــا » → « سببا »
    text = re.sub(r"\s+([\u064b-\u0652])", r"\1", text)              # « نق ّح » → « نقّح »
    text = re.sub(rf"(\d)([{_AR_LETTER}])", r"\1 \2", text)
    text = re.sub(rf"([{_AR_LETTER}])(\d)", r"\1 \2", text)
    text = re.sub(r"([a-zà-ÿ])-\n([a-zà-ÿ])", r"\1\2", text)  # césure française
    text = re.sub(r"[ \t]+", " ", text)
    text = "\n".join(line.strip() for line in text.splitlines())
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def normalize_arabic(text: str) -> str:
    """Aplatit l'arabe pour la recherche (pas pour l'affichage).

    Exemple : « الأَجْرُ » et « الاجر » deviennent identiques.
    """
    text = _TASHKEEL.sub("", text)
    text = text.replace(_TATWEEL, "")
    text = re.sub("[أإآٱ]", "ا", text)
    text = text.replace("ى", "ي").replace("ة", "ه")
    text = text.replace("ؤ", "و").replace("ئ", "ي")
    return text


def normalize_latin(text: str) -> str:
    """Minuscules + suppression des accents : « Congé » → « conge »."""
    text = text.lower().replace("œ", "oe").replace("æ", "ae")
    decomposed = unicodedata.normalize("NFD", text)
    return "".join(ch for ch in decomposed if unicodedata.category(ch) != "Mn")


def normalize_for_search(text: str) -> str:
    """Normalisation complète pour l'index de recherche (toutes langues)."""
    text = clean_text(text)
    text = normalize_arabic(text)
    text = normalize_latin(text)
    text = re.sub(r"[^\w\s\-]", " ", text)  # ponctuation → espace
    return re.sub(r"\s+", " ", text).strip()


# --- Détection de langue -------------------------------------------------------
_FR_WORDS = {
    "le", "la", "les", "des", "du", "de", "et", "est", "un", "une", "pour", "dans",
    "que", "qui", "au", "aux", "sur", "par", "travail", "contrat", "salarié",
    "employeur", "quel", "quelle", "combien", "peut", "être", "pas", "ce", "en",
}
_EN_WORDS = {
    "the", "of", "and", "is", "a", "an", "to", "in", "for", "on", "by", "what",
    "how", "many", "can", "work", "worker", "employer", "contract", "does",
    "are", "be", "with", "my", "which", "when", "days",
}


def arabic_ratio(text: str) -> float:
    """Part des lettres arabes parmi toutes les lettres (0 → 1)."""
    ar = len(_AR_LETTER_RE.findall(text))
    lat = len(_LATIN_LETTER_RE.findall(text))
    total = ar + lat
    return ar / total if total else 0.0


def detect_language(text: str) -> str:
    """Retourne 'ar', 'fr' ou 'en'.

    Règle simple et explicable :
    1. plus de 30 % de lettres arabes → 'ar'
    2. sinon on compte les mots-outils français et anglais → le plus fréquent gagne
    3. égalité → 'fr' (langue par défaut du projet)
    """
    if arabic_ratio(text) >= 0.3:
        return "ar"
    words = re.findall(r"[a-zà-ÿ']+", text.lower())
    words = [w.split("'")[-1] for w in words]  # « l'employeur » → « employeur »
    fr = sum(w in _FR_WORDS for w in words)
    en = sum(w in _EN_WORDS for w in words)
    return "en" if en > fr else "fr"