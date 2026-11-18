"""Étape 5 — Interface web Streamlit.

    streamlit run src/haqqi/ui/app.py

Une page de chat : on pose une question en arabe, français ou anglais ;
la réponse s'affiche dans le bon sens d'écriture, avec ses sources (article,
version, page) et, si l'article a changé, la comparaison des versions.
"""

from __future__ import annotations

import html
import re
from collections import Counter

import streamlit as st

from haqqi import service

st.set_page_config(page_title="Haqqi — حقّي", page_icon="⚖️", layout="wide")

EXAMPLES = [
    "Quel est l'âge minimum pour travailler en Tunisie ?",
    "Qu'est-ce qui a changé pour les CDD avec la loi 2025-9 ?",
    "ما هي المدة القصوى لفترة التجربة؟",
    "هل يجوز اللجوء إلى مناولة اليد العاملة؟",
    "What minimum age must a country set under Convention 138?",
    "How long is the annual paid leave?",
]
UI = {
    "fr": {"sources": "Sources", "compare": "Comparer les versions", "current": "en vigueur",
           "old": "remplacé", "page": "page"},
    "ar": {"sources": "المصادر", "compare": "مقارنة الصيغ", "current": "سارية المفعول",
           "old": "معوّضة", "page": "صفحة"},
    "en": {"sources": "Sources", "compare": "Compare versions", "current": "in force",
           "old": "replaced", "page": "page"},
}
ROUTES = {"lookup": "lecture d'un article", "compare": "comparaison de versions", "search": "recherche hybride"}

st.markdown("""
<style>
.hq-rtl { direction: rtl; text-align: right; font-size: 1.05rem; line-height: 1.8; }
.hq-ltr { direction: ltr; text-align: left; }
.hq-badge { display: inline-block; font-size: .78rem; padding: 1px 8px; border-radius: 10px;
            border: 1px solid rgba(128,128,128,.4); margin-right: 6px; }
.hq-current { color: #1d6b3a; border-color: #1d6b3a; }
.hq-old { color: #9a3b12; border-color: #9a3b12; }
</style>""", unsafe_allow_html=True)


@st.cache_resource(show_spinner="Chargement des articles et du modèle multilingue…")
def load_agent():
    return service.get_agent()


# Dans un texte arabe, « 63-2 » ou « [ct:63-2] » s'afficheraient à l'envers (« 2-63 »).
# On les isole pour qu'ils restent écrits de gauche à droite.
_LTR_PIECES = re.compile(r"\[[a-z0-9_@]+:[0-9a-z\-#]+\]|\d+(?:-\d+)+")


def isolate_ltr(text: str) -> str:
    """Version texte brut (titres) : marques Unicode LRI … PDI autour des numéros."""
    return _LTR_PIECES.sub(lambda m: f"\u2066{m.group(0)}\u2069", text)


def text_block(text: str, lang: str) -> None:
    """Affiche un texte dans le bon sens d'écriture (arabe : de droite à gauche)."""
    cls = "hq-rtl" if lang == "ar" else "hq-ltr"
    safe = html.escape(text)
    if lang == "ar":
        safe = _LTR_PIECES.sub(lambda m: f'<bdi dir="ltr">{m.group(0)}</bdi>', safe)
    st.markdown(f'<div class="{cls}">{safe.replace(chr(10), "<br>")}</div>', unsafe_allow_html=True)


def badge(is_current: bool, lang: str) -> str:
    ui = UI.get(lang, UI["fr"])
    cls, word = ("hq-current", ui["current"]) if is_current else ("hq-old", ui["old"])
    return f'<span class="hq-badge {cls}">{word}</span>'


def show_answer(out: dict, idx: int) -> None:
    lang = out["language"]
    ui = UI[lang]
    text_block(out["answer"], lang)
    st.caption(f"Langue : {lang} · chemin : {ROUTES.get(out['route'], out['route'])} · LLM : {out['llm']}")
    for w in out.get("warnings", []):
        st.caption(f"⚠ {w}")
    if not out["citations"]:
        return
    st.markdown(f"**{ui['sources']}**")
    store = load_agent().retriever.store
    for c in out["citations"]:
        title = isolate_ltr(f"[{c['article_key']}] {c['label']} — {c['version']} · {c['lang']} · {ui['page']} {c['page']}")
        with st.expander(title):
            st.markdown(badge(c["is_current"], lang), unsafe_allow_html=True)
            text_block(c["text"], c["lang"])
            versions = store.versions(c["article_key"])
            if len(versions) > 1 and st.checkbox(ui["compare"], key=f"cmp-{idx}-{c['article_key']}"):
                cols = st.columns(len(versions))
                for col, v in zip(cols, versions):
                    with col:
                        st.markdown(f"**{v['version']}** · {v['lang']} {badge(bool(v.get('is_current')), lang)}",
                                    unsafe_allow_html=True)
                        text_block(v["text"], v["lang"])


# --- Barre latérale ------------------------------------------------------------------------
agent = load_agent()
store = agent.retriever.store
with st.sidebar:
    st.title("⚖️ Haqqi · حقّي")
    st.caption("Assistant trilingue du droit du travail tunisien")
    counts = Counter(r["lang"] for r in store.records)
    st.markdown(f"**{len(store)} fiches** · arabe {counts['ar']} · français {counts['fr']} · anglais {counts['en']}")
    emb = agent.retriever.vectors.embedder.name if agent.retriever.vectors else "—"
    st.markdown(f"Modèle de langage : `{agent.llm_name}`  \nEmbeddings : `{emb}`")
    agent.mode = st.radio("Recherche", ["hybrid", "bm25", "vector"], horizontal=True,
                          help="hybrid = BM25 + vecteurs (RRF)")
    st.markdown("**Exemples**")
    for ex in EXAMPLES:
        if st.button(ex, width="stretch"):
            st.session_state["pending"] = ex
    st.divider()
    st.caption("Haqqi donne une information sur les textes de loi, pas un conseil juridique. "
               "حقّي يقدّم معلومة قانونية وليس استشارة قانونية.")

# --- Conversation -------------------------------------------------------------------------------
st.header("Posez votre question · اطرح سؤالك · Ask your question")
history = st.session_state.setdefault("history", [])
for i, turn in enumerate(history):
    with st.chat_message("user"):
        text_block(turn["question"], turn["out"]["language"])
    with st.chat_message("assistant"):
        show_answer(turn["out"], i)

question = st.chat_input("Arabe, français ou anglais…") or st.session_state.pop("pending", None)
if question:
    with st.chat_message("user"):
        text_block(question, "ar" if any("\u0600" <= ch <= "\u06ff" for ch in question) else "fr")
    with st.chat_message("assistant"):
        with st.spinner("Recherche des articles…"):
            out = service.answer_with_citations(question)
            for c in out["citations"]:   # texte complet de chaque article cité, pour l'affichage
                recs = [r for r in store.versions(c["article_key"]) if r["version"] == c["version"]
                        and r["lang"] == c["lang"]]
                c["text"] = recs[0]["text"] if recs else ""
        show_answer(out, len(history))
    history.append({"question": question, "out": out})