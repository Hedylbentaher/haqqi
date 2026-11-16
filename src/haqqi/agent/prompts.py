"""Les consignes données au modèle de langage, et la mise en forme des articles trouvés."""

from __future__ import annotations

from ..retrieval.store import citation_label

LANG_NAMES = {"ar": "arabe", "fr": "français", "en": "anglais"}

SYSTEM_PROMPT = """Tu es Haqqi, un assistant qui répond aux questions sur le droit du travail tunisien.

Règles :
1. Réponds UNIQUEMENT à partir des articles fournis. N'invente rien.
2. Réponds en {language_name}, même si les articles sont dans une autre langue.
3. Après chaque information, cite l'article entre crochets avec sa clé exacte, par exemple [ct:6-4] ou [c138:2].
4. Si plusieurs versions d'un article sont fournies, utilise la version marquée EN VIGUEUR,
   et signale le changement si la question porte sur l'avant / après.
5. Si les articles ne permettent pas de répondre, dis-le clairement en une phrase, sans citer d'article.
6. Réponds en 2 à 6 phrases, simplement."""

USER_PROMPT = """Articles trouvés :

{context}

Question : {question}"""


def format_context(records: list[dict], max_chars: int = 1800) -> str:
    """Chaque article : un en-tête avec sa clé, sa langue, sa version et son état, puis le texte."""
    blocks = []
    for r in records:
        state = "EN VIGUEUR" if r.get("is_current") else f"REMPLACÉ par {r.get('replaced_by')}"
        text = r["text"] if len(r["text"]) <= max_chars else r["text"][:max_chars] + " […]"
        blocks.append(f"[{r['article_key']}] {citation_label(r)} — {state}\n{text}")
    return "\n\n".join(blocks)