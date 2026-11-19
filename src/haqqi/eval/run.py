"""Évaluation complète de Haqqi.

    python -m haqqi.eval.run                        # recherche : bm25, vector, hybrid
    python -m haqqi.eval.run --generation           # + réponses de l'agent (LLM du fichier .env)
    python -m haqqi.eval.run --generation --delay 5 # pause entre deux questions (quota gratuit)
    python -m haqqi.eval.run --embedder hash        # sans télécharger le modèle (test rapide)

Résultats écrits dans results/ :
    retrieval.json · retrieval_details.jsonl · generation.jsonl · summary.md
"""

from __future__ import annotations

import argparse
import json
import time
from collections import defaultdict
from datetime import datetime, timezone

from .. import config
from ..agent.graph import HaqqiAgent
from ..ingestion.text_utils import detect_language
from ..retrieval.embeddings import VectorIndex, get_embedder
from ..retrieval.hybrid import MODES, Retriever
from ..retrieval.store import ArticleStore
from .metrics import facts_found, mean, recall_at_k, reciprocal_rank

KS = (1, 3, 5, 10)


def load_questions(path=config.QUESTIONS_FILE) -> list[dict]:
    with open(path, encoding="utf-8") as f:
        return [json.loads(line) for line in f if line.strip()]


# --- Recherche ------------------------------------------------------------------------------
def evaluate_retrieval(retriever: Retriever, questions: list[dict], modes=MODES) -> tuple[dict, list[dict]]:
    answerable = [q for q in questions if q["gold"]]
    details, results = [], {}
    for mode in modes:
        rows = []
        t0 = time.time()
        for q in answerable:
            ranked = retriever.search_keys(q["question"], k=max(KS), mode=mode)
            row = {"id": q["id"], "lang": q["lang"], "type": q["type"], "mode": mode,
                   "gold": q["gold"], "ranked": ranked, "rr": reciprocal_rank(ranked, q["gold"])}
            for k in KS:
                row[f"recall@{k}"] = recall_at_k(ranked, q["gold"], k)
            rows.append(row)
        elapsed = time.time() - t0
        details.extend(rows)

        def summarize(subset: list[dict]) -> dict:
            out = {f"recall@{k}": round(mean([r[f"recall@{k}"] for r in subset]), 3) for k in KS}
            out["mrr"] = round(mean([r["rr"] for r in subset]), 3)
            out["n"] = len(subset)
            return out

        by_lang = {lang: summarize([r for r in rows if r["lang"] == lang]) for lang in ("ar", "fr", "en")}
        by_type = {t: summarize([r for r in rows if r["type"] == t]) for t in sorted({r["type"] for r in rows})}
        results[mode] = {"all": summarize(rows), "by_lang": by_lang, "by_type": by_type,
                         "ms_per_query": round(1000 * elapsed / max(len(rows), 1), 1)}
    return results, details


# --- Réponses ---------------------------------------------------------------------------------
def evaluate_generation(agent: HaqqiAgent, questions: list[dict], delay: float = 0.0) -> tuple[dict, list[dict]]:
    rows = []
    for i, q in enumerate(questions):
        t0 = time.time()
        out = agent.ask(q["question"])
        cited = [c["article_key"] for c in out["citations"]]
        row = {
            "id": q["id"], "lang": q["lang"], "type": q["type"], "question": q["question"],
            "answer": out["answer"], "route": out["route"], "cited": cited, "gold": q["gold"],
            "seconds": round(time.time() - t0, 2), "warnings": out.get("warnings", []),
        }
        if q["gold"]:
            row["citation_ok"] = any(c in q["gold"] for c in cited)
            row["citation_precision"] = (sum(c in q["gold"] for c in cited) / len(cited)) if cited else 0.0
            row["facts_ok"] = facts_found(out["answer"], q["facts"]) if q["facts"] else None
        else:
            row["abstained"] = not cited
        row["language_ok"] = detect_language(out["answer"]) == q["lang"]
        rows.append(row)
        print(f"  [{i + 1}/{len(questions)}] {q['id']:<9} cité : {', '.join(cited) or '—'}")
        if delay and i < len(questions) - 1:
            time.sleep(delay)

    def rate(subset, key):
        vals = [r[key] for r in subset if r.get(key) is not None]
        return round(mean([float(v) for v in vals]), 3) if vals else None

    answerable = [r for r in rows if r["gold"]]
    summary = {
        "llm": agent.llm_name, "n": len(rows),
        "citation_ok": rate(answerable, "citation_ok"),
        "citation_precision": rate(answerable, "citation_precision"),
        "facts_ok": rate(answerable, "facts_ok"),
        "language_ok": rate(rows, "language_ok"),
        "out_of_scope_abstention": rate([r for r in rows if not r["gold"]], "abstained"),
        "by_lang": {lang: {"citation_ok": rate([r for r in answerable if r["lang"] == lang], "citation_ok"),
                           "facts_ok": rate([r for r in answerable if r["lang"] == lang], "facts_ok"),
                           "language_ok": rate([r for r in rows if r["lang"] == lang], "language_ok")}
                    for lang in ("ar", "fr", "en")},
        "by_type": {t: {"citation_ok": rate([r for r in answerable if r["type"] == t], "citation_ok"),
                        "facts_ok": rate([r for r in answerable if r["type"] == t], "facts_ok")}
                    for t in sorted({r["type"] for r in answerable})},
        "seconds_per_question": round(mean([r["seconds"] for r in rows]), 2),
    }
    return summary, rows


# --- Rapport markdown ---------------------------------------------------------------------------
def pct(x) -> str:
    return "—" if x is None else f"{100 * x:.1f} %"


def summary_markdown(meta: dict, retrieval: dict, generation: dict | None) -> str:
    lines = [f"# Résultats de l'évaluation Haqqi", "",
             f"- Date : {meta['date']}", f"- Questions : {meta['n_questions']} "
             f"({meta['n_answerable']} avec réponse, {meta['n_questions'] - meta['n_answerable']} hors sujet)",
             f"- Modèle d'embeddings : `{meta['embedder']}`", f"- Fiches : {meta['n_records']}", "",
             "## Recherche (toutes langues)", "",
             "| Méthode | Recall@1 | Recall@3 | Recall@5 | Recall@10 | MRR | ms / question |",
             "|---|---|---|---|---|---|---|"]
    for mode, r in retrieval.items():
        a = r["all"]
        lines.append(f"| {mode} | {pct(a['recall@1'])} | {pct(a['recall@3'])} | {pct(a['recall@5'])} | "
                     f"{pct(a['recall@10'])} | {a['mrr']:.3f} | {r['ms_per_query']} |")
    lines += ["", "## Recherche par langue de la question (Recall@5 · MRR)", "",
              "| Méthode | arabe | français | anglais |", "|---|---|---|---|"]
    for mode, r in retrieval.items():
        cells = [f"{pct(r['by_lang'][l]['recall@5'])} · {r['by_lang'][l]['mrr']:.3f}" for l in ("ar", "fr", "en")]
        lines.append(f"| {mode} | " + " | ".join(cells) + " |")
    types = sorted(next(iter(retrieval.values()))["by_type"])
    lines += ["", "## Recherche par type de question (Recall@5)", "",
              "| Méthode | " + " | ".join(types) + " |", "|---|" + "---|" * len(types)]
    for mode, r in retrieval.items():
        lines.append(f"| {mode} | " + " | ".join(pct(r["by_type"][t]["recall@5"]) for t in types) + " |")
    if generation:
        g = generation
        lines += ["", f"## Réponses de l'agent (LLM : `{g['llm']}`)", "",
                  "| Mesure | Valeur |", "|---|---|",
                  f"| Au moins une citation correcte | {pct(g['citation_ok'])} |",
                  f"| Précision des citations | {pct(g['citation_precision'])} |",
                  f"| Information attendue présente | {pct(g['facts_ok'])} |",
                  f"| Réponse dans la langue de la question | {pct(g['language_ok'])} |",
                  f"| Questions hors sujet : refus de répondre | {pct(g['out_of_scope_abstention'])} |",
                  f"| Secondes par question | {g['seconds_per_question']} |",
                  "", "| Langue | Citation correcte | Information présente | Bonne langue |", "|---|---|---|---|"]
        for lang, v in g["by_lang"].items():
            lines.append(f"| {lang} | {pct(v['citation_ok'])} | {pct(v['facts_ok'])} | {pct(v['language_ok'])} |")
    return "\n".join(lines) + "\n"


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description="Évaluation de Haqqi")
    parser.add_argument("--embedder", choices=["e5", "hash"], default=None)
    parser.add_argument("--modes", nargs="+", choices=MODES, default=list(MODES))
    parser.add_argument("--generation", action="store_true", help="évaluer aussi les réponses de l'agent")
    parser.add_argument("--no-llm", action="store_true", help="réponses extractives (sans LLM)")
    parser.add_argument("--delay", type=float, default=4.0, help="pause (s) entre deux questions LLM")
    parser.add_argument("--limit", type=int, default=None, help="n'évaluer que les N premières questions")
    args = parser.parse_args(argv)

    questions = load_questions()[: args.limit]
    store = ArticleStore.load()
    embedder = get_embedder(args.embedder or config.EMBEDDER)
    index, _ = VectorIndex.build(store.records, embedder)
    retriever = Retriever(store, index)

    print(f"Recherche : {len(questions)} questions, modes {', '.join(args.modes)} …")
    retrieval, details = evaluate_retrieval(retriever, questions, args.modes)
    generation = None
    config.RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    if args.generation:
        agent = HaqqiAgent(retriever, llm=None if args.no_llm else "auto")
        print(f"Réponses : LLM = {agent.llm_name} …")
        generation, gen_rows = evaluate_generation(agent, questions, 0 if agent.llm is None else args.delay)
        with open(config.RESULTS_DIR / "generation.jsonl", "w", encoding="utf-8") as f:
            f.writelines(json.dumps(r, ensure_ascii=False) + "\n" for r in gen_rows)

    meta = {"date": datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC"), "embedder": embedder.name,
            "n_questions": len(questions), "n_answerable": sum(1 for q in questions if q["gold"]),
            "n_records": len(store)}
    (config.RESULTS_DIR / "retrieval.json").write_text(
        json.dumps({"meta": meta, "retrieval": retrieval, "generation": generation}, ensure_ascii=False, indent=2),
        encoding="utf-8")
    with open(config.RESULTS_DIR / "retrieval_details.jsonl", "w", encoding="utf-8") as f:
        f.writelines(json.dumps(r, ensure_ascii=False) + "\n" for r in details)
    md = summary_markdown(meta, retrieval, generation)
    (config.RESULTS_DIR / "summary.md").write_text(md, encoding="utf-8")
    print("\n" + md)
    print(f"Fichiers écrits dans {config.RESULTS_DIR}")


if __name__ == "__main__":
    main()