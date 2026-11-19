"""Étape 5 — Interface web Streamlit.

    streamlit run src/haqqi/ui/app.py

Une page de chat : on pose une question en arabe, français ou anglais ;
la réponse s'affiche dans le bon sens d'écriture, avec ses sources (article,
version, page) et l'historique des versions de chaque article cité.
Les couleurs et les polices sont dans .streamlit/config.toml.
"""

from __future__ import annotations

import html
import re
from collections import Counter

import streamlit as st

from haqqi import service

st.set_page_config(page_title="Haqqi — حقّي", page_icon="⚖️", layout="wide")

# --- Textes de l'interface ---------------------------------------------------------------------
EXAMPLES = {
    "fr": ("En français", ["Quel est l'âge minimum pour travailler en Tunisie ?",
                           "Qu'est-ce qui a changé pour les CDD avec la loi 2025-9 ?"]),
    "en": ("In English", ["What minimum age must a country set under Convention 138?",
                          "How long is the annual paid leave?"]),
    "ar": ("بالعربية", ["ما هي المدة القصوى لفترة التجربة؟",
                       "هل يجوز اللجوء إلى مناولة اليد العاملة؟"]),
}
UI = {
    "fr": {"sources": "Sources", "compare": "Comparer les versions", "current": "en vigueur",
           "old": "remplacé", "page": "page", "history": "Versions de l'article"},
    "ar": {"sources": "المصادر", "compare": "مقارنة الصيغ", "current": "سارية المفعول",
           "old": "معوّضة", "page": "صفحة", "history": "صيغ الفصل"},
    "en": {"sources": "Sources", "compare": "Compare versions", "current": "in force",
           "old": "replaced", "page": "page", "history": "Versions of the article"},
}
LANG_WORDS = {
    "fr": {"ar": "arabe", "fr": "français", "en": "anglais"},
    "ar": {"ar": "بالعربية", "fr": "بالفرنسية", "en": "بالإنجليزية"},
    "en": {"ar": "Arabic", "fr": "French", "en": "English"},
}
VERSION_NAMES = {
    "edition_2004": {"fr": "édition 2004", "ar": "طبعة 2004", "en": "2004 edition"},
    "revision_1996": {"fr": "révision 1996", "ar": "مراجعة 1996", "en": "1996 revision"},
    "loi_2025_9": {"fr": "loi 2025-9", "ar": "القانون عدد 9 لسنة 2025", "en": "Law 2025-9"},
    "oit_1973": {"fr": "Convention 1973", "ar": "اتفاقية 1973", "en": "1973 Convention"},
}
DOCS = {   # registre du corpus (barre latérale)
    "ct_ar": ("Code du travail", "arabe, 2004"),
    "ct_fr": ("Code du travail", "français, 1996"),
    "loi_2025_9_ar": ("Loi n° 2025-9", "arabe, 2025"),
    "c138_en": ("Convention OIT n° 138", "anglais, 1973"),
}
SEP = {"fr": ", ", "en": ", ", "ar": "، "}
ROUTES = {"lookup": "Lecture d'un article", "compare": "Comparaison des versions"}
SEARCH_PILL = {"hybrid": "Recherche hybride", "bm25": "Recherche par mots exacts", "vector": "Recherche par le sens"}
MODES = {"hybrid": "hybride (mots + sens)", "bm25": "mots exacts (BM25)", "vector": "sens (e5)"}

st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Cairo:wght@600;700;800&family=IBM+Plex+Sans+Arabic:wght@400;500;600&display=swap');
:root { --hq-ink:#14212D; --hq-red:#B4232A; --hq-stone:#EEF1EE; --hq-rule:#D5DBD6;
        --hq-muted:#56636F; --hq-green:#1F6B4F; --hq-ochre:#8C5A12;
        --hq-display:'Cairo','IBM Plex Sans Arabic','Segoe UI',Tahoma,sans-serif;
        --hq-text:'IBM Plex Sans Arabic','Segoe UI',Tahoma,sans-serif; }
[data-testid="stMarkdownContainer"], [data-testid="stChatInput"] textarea, button, label,
[data-testid="stExpander"] summary { font-family: var(--hq-text); }
[data-testid="stMainBlockContainer"], .block-container { max-width: 1120px; padding-top: 2.5rem; }
[data-testid="stHeader"] { background: transparent; }

/* Barre latérale : nom, registre des textes */
.hq-brand { padding: .25rem 0 1.25rem; }
.hq-mark { font-family: var(--hq-display); font-weight: 800; font-size: 3.4rem; line-height: 1.6;
           color: #FFFFFF; text-align: left; }
.hq-name { font-family: var(--hq-display); font-weight: 700; font-size: 1.15rem; color: #F0A49C;
           margin-top: .1rem; }
.hq-tagline { font-size: .9rem; line-height: 1.5; color: #C3CCD4; margin: .6rem 0 0; }
.hq-side-title { font-family: var(--hq-display); font-weight: 700; font-size: .95rem; color: #FFFFFF;
                 margin: .25rem 0 .5rem; }
.hq-register { display: grid; grid-template-columns: 1fr auto; row-gap: .55rem; column-gap: .75rem;
               font-size: .88rem; }
.hq-register .doc { color: #E6EAEE; line-height: 1.3; }
.hq-register .doc small { display: block; color: #9AA8B4; font-size: .78rem; }
.hq-register .n { color: #FFFFFF; font-weight: 600; font-variant-numeric: tabular-nums; text-align: right; }
.hq-register .total { grid-column: 1 / -1; border-top: 1px solid #2E4152; padding-top: .55rem;
                      color: #C3CCD4; }
.hq-small { font-size: .8rem; line-height: 1.5; color: #9AA8B4; }

/* Accueil : la même invitation dans les deux sens d'écriture */
.hq-hero { display: grid; grid-template-columns: 1fr 1fr; align-items: end; gap: 2.5rem;
           padding-bottom: 1.5rem; border-bottom: 2px solid var(--hq-ink); }
.hq-hero .ltr { direction: ltr; text-align: left; }
.hq-hero .rtl { direction: rtl; text-align: right; }
.hq-hero h1 { font-family: var(--hq-display); font-weight: 800; font-size: 2.6rem; line-height: 1.15;
              color: var(--hq-ink); margin: 0; padding: 0; text-wrap: balance; }
.hq-hero .rtl h1 { font-size: 3rem; }
.hq-hero .en { font-size: 1.15rem; color: var(--hq-muted); margin: .6rem 0 0; }
.hq-hero .ar-sub { font-size: 1.15rem; color: var(--hq-muted); margin: .6rem 0 0; }
.hq-intro { max-width: 46rem; font-size: 1rem; line-height: 1.65; color: var(--hq-muted); margin: 1.25rem 0 .5rem; }
.hq-try { font-family: var(--hq-display); font-weight: 700; font-size: 1rem; color: var(--hq-ink);
          margin: 1.25rem 0 .25rem; }
.hq-try.rtl { direction: rtl; text-align: right; }

/* Conversation */
.hq-rtl { direction: rtl; text-align: right; font-size: 1.05rem; line-height: 1.85; }
.hq-ltr { direction: ltr; text-align: left; line-height: 1.7; }
.hq-question { font-family: var(--hq-display); font-weight: 700; font-size: 1.2rem; line-height: 1.5; }
.hq-answer { border-inline-start: 3px solid var(--hq-red); padding-inline-start: 1rem; margin: .25rem 0 .75rem; }
.hq-cite { display: inline-block; font-size: .82rem; font-weight: 600; color: var(--hq-red);
           border: 1px solid rgba(180,35,42,.45); border-radius: 6px; padding: 0 .4rem; margin: 0 .1rem;
           line-height: 1.5; white-space: nowrap; }
.hq-meta { display: flex; flex-wrap: wrap; gap: .4rem; margin: 0 0 .9rem; }
.hq-meta.rtl { justify-content: flex-end; }
.hq-pill { font-size: .78rem; color: var(--hq-muted); background: var(--hq-stone); border-radius: 999px;
           padding: .1rem .6rem; }
.hq-sources { font-family: var(--hq-display); font-weight: 700; font-size: 1rem; margin: .5rem 0 .25rem; }
.hq-badge { display: inline-block; font-size: .78rem; font-weight: 600; padding: .05rem .55rem;
            border-radius: 999px; border: 1px solid; margin-inline-end: .4rem; }
.hq-current { color: var(--hq-green); border-color: var(--hq-green); background: #E6F1EC; }
.hq-old { color: var(--hq-ochre); border-color: #C9A46A; background: #FBF4E8; }
.hq-docline { font-size: .85rem; color: var(--hq-muted); margin: .1rem 0 .6rem; }

/* Historique des versions d'un article, de la plus ancienne à la plus récente */
.hq-rail-title { font-size: .8rem; color: var(--hq-muted); margin: .2rem 0 .35rem; }
.hq-rail { display: flex; flex-wrap: wrap; gap: 0; list-style: none; padding: 0; margin: 0 0 .9rem; }
.hq-rail li { position: relative; flex: 1 1 9rem; padding-block: .55rem .5rem; padding-inline: 1.4rem .8rem;
              margin: 0; border-top: 3px solid #C9A46A; }
.hq-rail li::before { content: ""; position: absolute; inset-inline-start: .35rem; top: -.5rem;
                      width: .7rem; height: .7rem;
                      border-radius: 50%; background: #fff; border: 2px solid #C9A46A; }
.hq-rail li.now { border-top-color: var(--hq-green); }
.hq-rail li.now::before { background: var(--hq-green); border-color: var(--hq-green); }
.hq-rail li.shown { background: var(--hq-stone); border-radius: 0 0 8px 8px; }
.hq-rail .year { display: block; font-family: var(--hq-display); font-weight: 700; font-size: 1.05rem;
                 color: var(--hq-ink); }
.hq-rail .what { display: block; font-size: .8rem; color: var(--hq-muted); line-height: 1.4; }
.hq-rail .state { display: block; font-size: .78rem; font-weight: 600; color: var(--hq-ochre); }
.hq-rail li.now .state { color: var(--hq-green); }

/* Exemples : texte complet sur plusieurs lignes ; la colonne arabe est écrite de droite à gauche */
[data-testid="stMainBlockContainer"] .stButton button { justify-content: flex-start; text-align: start;
    min-height: 3.9rem; height: auto; padding: .55rem .9rem; border-color: var(--hq-rule); }
[data-testid="stMainBlockContainer"] .stButton button > div { width: 100%; justify-content: flex-start; }
[data-testid="stMainBlockContainer"] .stButton button p { white-space: normal; overflow: visible;
    text-overflow: clip; line-height: 1.45; text-align: start; width: 100%; }
[data-testid="stMainBlockContainer"] .stButton button:hover { border-color: var(--hq-red); color: var(--hq-red); }
[data-testid="stHorizontalBlock"] > div:nth-child(3) .stButton button { direction: rtl; text-align: right; }

@media (max-width: 760px) {
  .hq-hero { grid-template-columns: 1fr; gap: 1rem; }
  .hq-hero h1 { font-size: 2rem; }
  .hq-hero .rtl h1 { font-size: 2.3rem; }
}
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


def _rich(text: str, lang: str) -> str:
    """Texte échappé → HTML : citations [ct:53] en étiquettes, numéros isolés en arabe."""
    def piece(m: re.Match) -> str:
        s = m.group(0)
        if s.startswith("["):
            return f'<bdi dir="ltr" class="hq-cite">{s[1:-1]}</bdi>'
        return f'<bdi dir="ltr">{s}</bdi>' if lang == "ar" else s
    return _LTR_PIECES.sub(piece, html.escape(text)).replace("\n", "<br>")


def text_block(text: str, lang: str, extra: str = "") -> None:
    """Affiche un texte dans le bon sens d'écriture (arabe : de droite à gauche)."""
    cls = "hq-rtl" if lang == "ar" else "hq-ltr"
    st.markdown(f'<div class="{cls} {extra}">{_rich(text, lang)}</div>', unsafe_allow_html=True)


def badge(is_current: bool, lang: str) -> str:
    ui = UI.get(lang, UI["fr"])
    cls, word = ("hq-current", ui["current"]) if is_current else ("hq-old", ui["old"])
    return f'<span class="hq-badge {cls}">{word}</span>'


def version_name(version: str, lang: str) -> str:
    return VERSION_NAMES.get(version, {}).get(lang, version)


def version_rail(versions: list[dict], shown: dict, lang: str) -> str:
    """Les versions d'un article dans l'ordre du temps ; celle qui est affichée est surlignée."""
    ui = UI.get(lang, UI["fr"])
    stops = []
    for v in sorted(versions, key=lambda r: r.get("date") or ""):
        cls = " ".join(c for c in ("now" if v.get("is_current") else "",
                                   "shown" if v["id"] == shown.get("id") else "") if c)
        stops.append(
            f'<li class="{cls}"><span class="year">{(v.get("date") or "")[:4]}</span>'
            f'<span class="what">{html.escape(version_name(v["version"], lang))}{SEP[lang]}'
            f'{LANG_WORDS[lang][v["lang"]]}</span>'
            f'<span class="state">{ui["current"] if v.get("is_current") else ui["old"]}</span></li>')
    side = "rtl" if lang == "ar" else "ltr"
    return (f'<div class="hq-{side}" dir="{side}"><p class="hq-rail-title">{ui["history"]}</p>'
            f'<ol class="hq-rail" dir="{side}">{"".join(stops)}</ol></div>')


def show_answer(out: dict, idx: int) -> None:
    lang = out["language"]
    ui = UI[lang]
    text_block(out["answer"], lang, "hq-answer")
    route = ROUTES.get(out["route"]) or SEARCH_PILL.get(out.get("mode", ""), "Recherche")
    pills = [f"Réponse en {LANG_WORDS['fr'][lang]}", route, out["llm"]]
    meta_cls = "hq-meta rtl" if lang == "ar" else "hq-meta"
    st.markdown(f'<div class="{meta_cls}">' + "".join(f'<span class="hq-pill">{html.escape(p)}</span>'
                                                 for p in pills) + "</div>", unsafe_allow_html=True)
    for w in out.get("warnings", []):
        st.caption(f"⚠ {w}")
    if not out["citations"]:
        return
    side = "hq-rtl" if lang == "ar" else "hq-ltr"
    st.markdown(f'<p class="hq-sources {side}">{ui["sources"]}</p>', unsafe_allow_html=True)
    store = load_agent().retriever.store
    for c in out["citations"]:
        rest = (f"{c['label']} — {version_name(c['version'], lang)}{SEP[lang]}"
                f"{LANG_WORDS[lang][c['lang']]}{SEP[lang]}{ui['page']} {c['page']}")
        if lang == "ar":                     # titre arabe : écrit de droite à gauche après la clé
            rest = f"\u2067{rest}\u2069"
        title = isolate_ltr(f"[{c['article_key']}] {rest}")
        with st.expander(title):
            versions = store.versions(c["article_key"])
            shown = next((v for v in versions if v["version"] == c["version"] and v["lang"] == c["lang"]), {})
            st.markdown(f'<div class="{side}">{badge(c["is_current"], lang)}'
                        f'<span class="hq-docline">{html.escape(shown.get("title", ""))}</span></div>',
                        unsafe_allow_html=True)
            if len(versions) > 1:
                st.markdown(version_rail(versions, shown, lang), unsafe_allow_html=True)
            text_block(c["text"], c["lang"])
            if len(versions) > 1 and st.checkbox(ui["compare"], key=f"cmp-{idx}-{c['article_key']}"):
                cols = st.columns(len(versions))
                for col, v in zip(cols, sorted(versions, key=lambda r: r.get("date") or "")):
                    with col:
                        st.markdown(f"**{version_name(v['version'], lang)}** "
                                    f"{badge(bool(v.get('is_current')), lang)}", unsafe_allow_html=True)
                        text_block(v["text"], v["lang"])


def language_of(question: str) -> str:
    return "ar" if any("\u0600" <= ch <= "\u06ff" for ch in question) else "fr"


# --- Barre latérale ------------------------------------------------------------------------
agent = load_agent()
store = agent.retriever.store
history = st.session_state.setdefault("history", [])
with st.sidebar:
    st.markdown('<div class="hq-brand"><div class="hq-mark" dir="rtl">حقّي</div>'
                '<div class="hq-name">Haqqi</div>'
                '<p class="hq-tagline">Le droit du travail tunisien, en arabe, en français et en anglais.</p></div>',
                unsafe_allow_html=True)
    per_doc = Counter(r["doc_id"] for r in store.records)
    order = [d for d in DOCS if d in per_doc] + [d for d in per_doc if d not in DOCS]
    rows = []
    for doc_id in order:
        n = per_doc[doc_id]
        first = next(r for r in store.records if r["doc_id"] == doc_id)
        name, meta = DOCS.get(doc_id, (first.get("title", doc_id)[:40],
                                       f"{LANG_WORDS['fr'][first['lang']]}, {(first.get('date') or '')[:4]}"))
        rows.append(f'<span class="doc">{html.escape(name)}<small>{html.escape(meta)}</small></span>'
                    f'<span class="n">{n}</span>')
    n_current = sum(1 for r in store.records if r.get("is_current"))
    st.markdown('<p class="hq-side-title">Les textes</p><div class="hq-register">' + "".join(rows)
                + f'<span class="total">{len(store)} fiches, dont {n_current} en vigueur</span></div>',
                unsafe_allow_html=True)
    st.write("")
    agent.mode = st.radio("Méthode de recherche", list(MODES), format_func=MODES.get)
    emb = agent.retriever.vectors.embedder.name if agent.retriever.vectors else "—"
    st.markdown(f'<p class="hq-small">Rédaction : {html.escape(agent.llm_name)}<br>'
                f'Recherche par le sens : {html.escape(emb)}</p>', unsafe_allow_html=True)
    new_chat = st.empty()        # rempli en bas de page, dès la première réponse
    st.markdown('<p class="hq-small">Haqqi informe sur les textes de loi ; il ne remplace pas un avocat.</p>'
                '<p class="hq-small" dir="rtl" style="text-align:right">حقّي يقدّم معلومة قانونية '
                'وليس استشارة قانونية.</p>', unsafe_allow_html=True)

# --- Accueil (avant la première question) --------------------------------------------------------
welcome = st.empty()
if not history:
    with welcome.container():
        st.markdown(
            '<div class="hq-hero">'
            '<div class="ltr"><h1>Posez votre question sur le droit du travail.</h1>'
            '<p class="en">Ask your question about Tunisian labour law.</p></div>'
            '<div class="rtl"><h1>اطرح سؤالك عن قانون الشغل.</h1>'
            '<p class="ar-sub">بالعربية أو بالفرنسية أو بالإنجليزية</p></div></div>'
            '<p class="hq-intro">Haqqi lit le Code du travail, la loi n° 2025-9 et la Convention OIT n° 138. '
            "Il répond dans la langue de votre question et cite l'article exact, dans sa version en vigueur.</p>",
            unsafe_allow_html=True)
        for col, lang in zip(st.columns(3), ("fr", "en", "ar")):
            heading, questions = EXAMPLES[lang]
            with col:
                rtl = " rtl" if lang == "ar" else ""
                st.markdown(f'<p class="hq-try{rtl}">{heading}</p>', unsafe_allow_html=True)
                for ex in questions:
                    if st.button(ex, key=f"ex-{ex}", width="stretch"):
                        st.session_state["pending"] = ex

# --- Conversation -------------------------------------------------------------------------------
for i, turn in enumerate(history):
    with st.chat_message("user", avatar=":material/person:"):
        text_block(turn["question"], language_of(turn["question"]), "hq-question")
    with st.chat_message("assistant", avatar=":material/balance:"):
        show_answer(turn["out"], i)

question = (st.chat_input("Écrivez votre question, en arabe, en français ou en anglais")
            or st.session_state.pop("pending", None))
if question:
    welcome.empty()
    with st.chat_message("user", avatar=":material/person:"):
        text_block(question, language_of(question), "hq-question")
    with st.chat_message("assistant", avatar=":material/balance:"):
        with st.spinner("Recherche des articles…"):
            out = service.answer_with_citations(question)
            out["mode"] = agent.mode
            for c in out["citations"]:   # texte complet de chaque article cité, pour l'affichage
                recs = [r for r in store.versions(c["article_key"]) if r["version"] == c["version"]
                        and r["lang"] == c["lang"]]
                c["text"] = recs[0]["text"] if recs else ""
        show_answer(out, len(history))
    history.append({"question": question, "out": out})

if history and new_chat.button("Nouvelle conversation", width="stretch"):
    st.session_state["history"] = []
    st.rerun()