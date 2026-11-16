"""L'agent Haqqi, construit avec LangGraph.

Le graphe (chaque case est une fonction, l'état circule de case en case) :

    START → langue → aiguillage ─┬─→ lecture   (« article 53 », « الفصل 6-4 »)  ─┐
                                 ├─→ versions  (« avant / après 2025 »)         ├─→ rédaction → vérification → END
                                 └─→ recherche (tout le reste)                  ─┘

- langue      : arabe, français ou anglais (règle simple, étape 1)
- aiguillage  : repère un numéro d'article ou une question sur les versions
- rédaction   : LLM (Gemini / Groq) ou, sans clé, réponse extractive
- vérification: une citation qui ne vient pas des articles trouvés est supprimée
"""

from __future__ import annotations

import re
from typing import TypedDict

from langgraph.graph import END, START, StateGraph

from ..ingestion.splitter import canonical_number
from ..ingestion.text_utils import detect_language, normalize_for_search
from ..retrieval.embeddings import HashEmbedder
from ..retrieval.hybrid import Retriever
from .llm import describe, get_chat_model
from .prompts import LANG_NAMES, SYSTEM_PROMPT, USER_PROMPT, format_context


class AgentState(TypedDict, total=False):
    question: str
    language: str              # langue de la question : ar | fr | en
    route: str                 # lookup | compare | search
    article_key: str | None    # article cité dans la question, ex. « ct:53 »
    hits: list[dict]           # fiches données au modèle (le « contexte »)
    answer: str
    citations: list[dict]
    warnings: list[str]


# --- Repérer un article dans la question -------------------------------------------------
_REF_PATTERNS = [
    re.compile(r"\b(?:article|art\.?)\s*(\d+(?:\s*-\s*\d+)?)(?:\s*(bis|ter|quater|quinquies))?\b", re.I),
    re.compile(r"(?:الفصل|فصل)\s*(\d+(?:\s*-\s*\d+)?)(?:\s*(مكرر))?"),
]
_CONVENTION_WORDS = re.compile(r"convention|138|اتفاقي", re.I)

# Mots qui signalent une question sur les versions (texte normalisé : sans accents, ة→ه…)
_VERSION_WORDS = [
    "reforme", "2025", "ancienne version", "ancien texte", "nouvelle version", "modifie", "a change",
    "avant et apres", "avant la loi", "تنقيح", "نقح", "عدل", "الصيغه القديمه", "الصيغه الجديده",
    "قبل وبعد", "تغير", "amend", "reform", "old version", "new version", "changed", "before and after",
]


def find_article_reference(question: str) -> str | None:
    """« Que dit l'article 6-4 ? » → « ct:6-4 » ; « Article 2 of the Convention » → « c138:2 »."""
    for pattern in _REF_PATTERNS:
        m = pattern.search(question)
        if m:
            code = "c138" if _CONVENTION_WORDS.search(question) else "ct"
            return f"{code}:{canonical_number(m.group(1), m.group(2))}"
    return None


# Abréviations courantes → les mots du texte de loi (sinon la recherche par mots ne les trouve pas)
_ABBREVIATIONS = [
    (re.compile(r"\bCDD\b", re.I), "CDD contrat de travail à durée déterminée"),
    (re.compile(r"\bCDI\b", re.I), "CDI contrat de travail à durée indéterminée"),
]


def expand_abbreviations(question: str) -> str:
    """« Un CDD ? » → « Un CDD contrat de travail à durée déterminée ? »"""
    for pattern, words in _ABBREVIATIONS:
        question = pattern.sub(words, question)
    return question


def asks_about_versions(question: str) -> bool:
    q = normalize_for_search(question)
    return any(w in q for w in _VERSION_WORDS)


# --- Étiquettes de citation dans la langue de la réponse ----------------------------------
_NAMES = {
    "ct": {"fr": "Code du travail, art.", "ar": "مجلة الشغل، الفصل", "en": "Labour Code, art."},
    "c138": {"fr": "Convention OIT n° 138, art.", "ar": "اتفاقية العمل الدولية رقم 138، الفصل",
             "en": "ILO Convention No. 138, art."},
    "loi_2025_9": {"fr": "Loi n° 2025-9, art.", "ar": "القانون عدد 9 لسنة 2025، الفصل", "en": "Law No. 2025-9, art."},
}


def label_for(rec: dict, lang: str) -> str:
    code, number = rec["article_key"].split(":", 1)
    names = _NAMES.get(code.split("@")[0], {"fr": code, "ar": code, "en": code})
    return f"{names.get(lang, names['fr'])} {number}"


_TEMPLATES = {
    "fr": {"intro": "D'après {label} : « {text} »", "orig": "(texte original en {lang})",
           "versions": "Versions de {label} :", "ver": "• {version} ({state}) : « {text} »",
           "current": "en vigueur", "old": "remplacée", "none": "Je n'ai pas trouvé d'article qui répond à cette question.",
           "lang_names": {"ar": "arabe", "fr": "français", "en": "anglais"}},
    "ar": {"intro": "حسب {label}: «{text}»", "orig": "(النص الأصلي باللغة {lang})",
           "versions": "صيغ {label}:", "ver": "• {version} ({state}): «{text}»",
           "current": "سارية المفعول", "old": "معوّضة", "none": "لم أجد فصلا يجيب عن هذا السؤال.",
           "lang_names": {"ar": "العربية", "fr": "الفرنسية", "en": "الإنجليزية"}},
    "en": {"intro": "According to {label}: “{text}”", "orig": "(original text in {lang})",
           "versions": "Versions of {label}:", "ver": "• {version} ({state}): “{text}”",
           "current": "in force", "old": "replaced", "none": "I could not find an article that answers this question.",
           "lang_names": {"ar": "Arabic", "fr": "French", "en": "English"}},
}

_CITE = re.compile(r"\[([a-z0-9_@]+:[0-9a-z\-#]+)\]")


def _snippet(text: str, n: int = 320) -> str:
    text = " ".join(text.split())
    return text if len(text) <= n else text[:n].rsplit(" ", 1)[0] + " …"


class HaqqiAgent:
    def __init__(self, retriever: Retriever | None = None, llm="auto", mode: str = "hybrid", k: int = 6):
        self._retriever = retriever
        self.llm = get_chat_model() if llm == "auto" else llm
        self.mode = mode
        self.k = k
        self.graph = self._build()

    @property
    def retriever(self) -> Retriever:
        if self._retriever is None:
            self._retriever = Retriever.load()
        return self._retriever

    @property
    def llm_name(self) -> str:
        return describe(self.llm)

    # ---- les cases du graphe ------------------------------------------------------------
    def _detect_language(self, s: AgentState) -> AgentState:
        return {"language": detect_language(s["question"]), "warnings": []}

    def _route(self, s: AgentState) -> AgentState:
        key = find_article_reference(s["question"])
        if key and key not in self.retriever.store.by_key:
            key = None
        if asks_about_versions(s["question"]):
            return {"route": "compare", "article_key": key}
        return {"route": "lookup" if key else "search", "article_key": key}

    def _search_hits(self, question: str, current_only: bool = True, k: int | None = None) -> list[dict]:
        vectors = self.retriever.vectors
        # Le modèle « hash » ne comprend pas le sens : dans ce cas BM25 seul est plus fiable.
        semantic = vectors is not None and not isinstance(vectors.embedder, HashEmbedder)
        mode = self.mode if semantic else "bm25"
        return [h.record for h in self.retriever.search(expand_abbreviations(question), k=k or self.k, mode=mode,
                                                        current_only=current_only)]

    def _lookup(self, s: AgentState) -> AgentState:
        hits = self.retriever.store.current(s["article_key"])
        if not hits:   # article abrogé : on montre quand même ses versions
            hits = self.retriever.store.versions(s["article_key"])
        return {"hits": hits}

    def _compare(self, s: AgentState) -> AgentState:
        key = s.get("article_key")
        if key is None:   # pas de numéro : on cherche l'article dans les résultats
            versions = self.retriever.store.versions
            hits = self._search_hits(s["question"], current_only=False, k=20)   # on regarde plus loin

            def replaced_by_a_law(k: str) -> bool:   # une version remplacée par une loi (ex. 2025-9)
                return any(v.get("replaced_by") not in (None, "abrogé") for v in versions(k))

            def has_several_versions(k: str) -> bool:
                return len(versions(k)) > 1

            # 1er choix : un article vraiment modifié ; sinon : un article en plusieurs versions
            for wanted in (replaced_by_a_law, has_several_versions):
                key = next((r["article_key"] for r in hits if wanted(r["article_key"])), None)
                if key is not None:
                    break
        if key is None:
            return {"route": "search", "hits": self._search_hits(s["question"])}
        return {"article_key": key, "hits": self.retriever.store.versions(key)}

    def _search(self, s: AgentState) -> AgentState:
        return {"hits": self._search_hits(s["question"])}

    def _generate(self, s: AgentState) -> AgentState:
        if self.llm is not None:
            try:
                return {"answer": self._llm_answer(s)}
            except Exception as exc:   # quota, réseau… → la démo continue en mode extractif
                return {"answer": self._extractive_answer(s),
                        "warnings": s.get("warnings", []) + [f"LLM indisponible ({type(exc).__name__}) : réponse extractive."]}
        return {"answer": self._extractive_answer(s)}

    def _verify(self, s: AgentState) -> AgentState:
        answer, hits = s["answer"], s.get("hits", [])
        valid = {h["article_key"] for h in hits}
        warnings = list(s.get("warnings", []))
        cited: list[str] = []
        for key in _CITE.findall(answer):
            if key in valid:
                if key not in cited:
                    cited.append(key)
            else:
                answer = answer.replace(f"[{key}]", "")
                warnings.append(f"Citation supprimée : [{key}] ne fait pas partie des articles trouvés.")
        lang = s["language"]
        citations = []
        for key in cited:
            versions = [h for h in hits if h["article_key"] == key]
            best = sorted(versions, key=lambda h: (not h.get("is_current"), h["lang"] != lang))[0]
            citations.append({
                "article_key": key, "label": label_for(best, lang), "lang": best["lang"],
                "version": best["version"], "is_current": bool(best.get("is_current")),
                "replaced_by": best.get("replaced_by"), "page": best.get("page"),
                "title": best.get("title", ""), "text": best["text"],
            })
        answer = re.sub(r"[ \t]+([.,;،])", r"\1", re.sub(r"[ \t]{2,}", " ", answer))
        return {"answer": answer.strip(), "citations": citations, "warnings": warnings}

    # ---- rédaction ------------------------------------------------------------------------
    def _llm_answer(self, s: AgentState) -> str:
        from langchain_core.messages import HumanMessage, SystemMessage
        messages = [
            SystemMessage(SYSTEM_PROMPT.format(language_name=LANG_NAMES[s["language"]])),
            HumanMessage(USER_PROMPT.format(context=format_context(s.get("hits", [])), question=s["question"])),
        ]
        content = self.llm.invoke(messages).content
        if isinstance(content, list):   # certains modèles renvoient des morceaux
            content = "".join(p.get("text", "") if isinstance(p, dict) else str(p) for p in content)
        return str(content)

    def _extractive_answer(self, s: AgentState) -> str:
        """Sans LLM : on cite le texte des articles trouvés, dans la langue de la question si possible."""
        lang, hits = s["language"], s.get("hits", [])
        t = _TEMPLATES[lang]
        if not hits:
            return t["none"]
        if s.get("route") == "compare":
            key = hits[0]["article_key"]
            lines = [t["versions"].format(label=label_for(hits[0], lang))]
            for h in hits:   # versions dans la langue de la question + version(s) en vigueur
                if h["lang"] == lang or h.get("is_current"):
                    state = t["current"] if h.get("is_current") else t["old"]
                    line = t["ver"].format(version=h["version"], state=state, text=_snippet(h["text"], 220))
                    if h["lang"] != lang:
                        line += " " + t["orig"].format(lang=t["lang_names"][h["lang"]])
                    lines.append(line)
            return "\n".join(lines) + f" [{key}]"
        parts, seen = [], []
        for h in hits:
            if h["article_key"] in seen:
                continue
            seen.append(h["article_key"])
            same_lang = [x for x in hits if x["article_key"] == h["article_key"] and x["lang"] == lang]
            rec = same_lang[0] if same_lang else h
            line = t["intro"].format(label=label_for(rec, lang), text=_snippet(rec["text"]))
            if rec["lang"] != lang:
                line += " " + t["orig"].format(lang=t["lang_names"][rec["lang"]])
            parts.append(f"{line} [{rec['article_key']}]")
            if len(parts) == 2:
                break
        return "\n\n".join(parts)

    # ---- assemblage --------------------------------------------------------------------------
    def _build(self):
        g = StateGraph(AgentState)
        g.add_node("langue", self._detect_language)
        g.add_node("aiguillage", self._route)
        g.add_node("lecture", self._lookup)
        g.add_node("versions", self._compare)
        g.add_node("recherche", self._search)
        g.add_node("redaction", self._generate)
        g.add_node("verification", self._verify)
        g.add_edge(START, "langue")
        g.add_edge("langue", "aiguillage")
        g.add_conditional_edges("aiguillage", lambda s: s["route"],
                                {"lookup": "lecture", "compare": "versions", "search": "recherche"})
        for node in ("lecture", "versions", "recherche"):
            g.add_edge(node, "redaction")
        g.add_edge("redaction", "verification")
        g.add_edge("verification", END)
        return g.compile()

    def ask(self, question: str) -> dict:
        """Pose une question. Retourne answer, citations, language, route, hits, warnings."""
        return self.graph.invoke({"question": question})