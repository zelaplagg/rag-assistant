"""Evaluate StudyMate against the golden set.

    python -m src.eval                 # retrieval only: fast, free, no LLM
    python -m src.eval --answers       # also generate answers with the configured LLM
    python -m src.eval --json out.json --min-hit 0.8

Retrieval is scored per case: a retrieved chunk is *relevant* if it comes from an
expected source and contains an `evidence` phrase (so scores do not depend on
chunk boundaries). Metrics: hit@k, MRR and evidence recall. Unanswerable cases are
excluded from those; instead we record the top similarity score, which is what a
"not in the notes" threshold has to separate.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import statistics
import sys
from collections import defaultdict
from typing import Callable

from .golden import GoldenCase, contains_evidence, load_golden

_NEG = r"(?:do(?:es)?\s*n[\u2019']t|do(?:es)?\s+not|(?:is|are)\s*n[\u2019']t|(?:is|are)\s+not|can[\u2019']?not|can[\u2019']t|couldn[\u2019']t|could\s+not|unable\s+to)"
ABSTAIN_PATTERNS = [
    # "the notes don't/do not <verb>" within a few words: contain, state, explain, mention, say, cover, ...
    _NEG + r"(?:\s+\w+){0,3}?\s+(?:contain|mention|say|state|explain|describe|define|cover|include|provide|specify|"
           r"list|give|have|address|discuss|compare|find|answer|know|offer)",
    r"no\s+(?:information|mention|details?)",
    r"not\s+(?:found\s+)?in\s+(?:the|your)\s+(?:provided\s+)?notes",
    r"(?:немає|не\s+містя|не\s+згаду|не\s+знайш|не\s+вказан|не\s+опису|не\s+пояснює)",
]
_ABSTAIN = re.compile("|".join(ABSTAIN_PATTERNS), re.IGNORECASE)


# ---------- pure scoring functions (no I/O) ----------

def is_relevant(case: GoldenCase, source: str, text: str) -> bool:
    return source in case.expected_sources and any(contains_evidence(text, e) for e in case.evidence)


def score_retrieval(case: GoldenCase, passages: list) -> dict:
    """passages: objects with .source .text .score, best first."""
    rank = next((i for i, p in enumerate(passages, 1) if is_relevant(case, p.source, p.text)), None)
    covered = sum(
        any(p.source in case.expected_sources and contains_evidence(p.text, e) for p in passages)
        for e in case.evidence
    )
    return {
        "rank": rank,
        "evidence_recall": covered / len(case.evidence) if case.evidence else None,
        "relevant": [is_relevant(case, p.source, p.text) for p in passages],
        "top_score": passages[0].score if passages else None,
        "retrieved": [(p.source, p.score) for p in passages],
    }


def is_abstention(answer: str) -> bool:
    return bool(_ABSTAIN.search(answer))


def score_answer(case: GoldenCase, answer: str) -> dict:
    abstained = is_abstention(answer)
    if not case.answerable:
        return {"abstained": abstained, "ok": abstained}
    low = answer.lower()
    missing = [k for k in case.must_include if k.lower() not in low]
    cited = any(s.lower() in low for s in case.expected_sources)
    return {"abstained": abstained, "missing_keywords": missing, "cited_expected_source": cited,
            "ok": not missing and not abstained}


JUDGE_SYSTEM = (
    "You are a strict grader of answers to questions about study notes. You get a question, a "
    "reference answer and a candidate answer. The candidate is CORRECT if it conveys the key facts "
    "of the reference answer and does not contradict it. The language of the candidate does not "
    "matter (a Ukrainian answer can be correct for an English reference). Extra correct detail is "
    "fine. An answer that says the information is missing is INCORRECT here. "
    'Reply with JSON only: {"correct": true|false, "reason": "<one short sentence>"}'
)


def parse_judge(raw: str) -> dict:
    """Pull {"correct": bool, "reason": str} out of a model reply, tolerating code fences and chatter."""
    m = re.search(r"\{.*?\}", raw, re.DOTALL)
    if not m:
        raise ValueError(f"judge did not return JSON: {raw[:80]!r}")
    data = json.loads(m.group(0))
    if not isinstance(data.get("correct"), bool):
        raise ValueError("judge JSON has no boolean 'correct'")
    return {"correct": data["correct"], "reason": str(data.get("reason", ""))[:200]}


def make_llm_judge(chat_fn: Callable) -> Callable:
    def judge(case: GoldenCase, answer: str) -> dict:
        prompt = (f"Question: {case.question}\n\nReference answer: {case.reference_answer}\n\n"
                  f"Candidate answer: {answer}")
        return parse_judge(chat_fn(JUDGE_SYSTEM, prompt, temperature=0.0))
    return judge


def _mean(xs: list[float]) -> float | None:
    return sum(xs) / len(xs) if xs else None


def aggregate(results: list[dict], ks: list[int]) -> dict:
    """results: per-case dicts with 'category', 'answerable', 'retrieval' (+ optional 'answer')."""
    def block(rows: list[dict]) -> dict:
        ans = [r for r in rows if r["answerable"]]
        out: dict = {"n": len(rows), "n_answerable": len(ans)}
        for k in ks:
            out[f"hit@{k}"] = _mean([1.0 if r["retrieval"]["rank"] and r["retrieval"]["rank"] <= k else 0.0 for r in ans])
        kmax = max(ks)
        out[f"prec@{kmax}"] = _mean([sum(r["retrieval"]["relevant"][:kmax]) / kmax for r in ans])
        out["mrr"] = _mean([1 / r["retrieval"]["rank"] if r["retrieval"]["rank"] else 0.0 for r in ans])
        out["evidence_recall"] = _mean([r["retrieval"]["evidence_recall"] for r in ans])
        with_ans = [r for r in rows if "answer" in r]
        if with_ans:
            a_ans = [r for r in with_ans if r["answerable"]]
            a_un = [r for r in with_ans if not r["answerable"]]
            out["answer_ok"] = _mean([1.0 if r["answer"]["ok"] else 0.0 for r in a_ans])
            judged = [r["answer"]["judge"]["correct"] for r in a_ans if r["answer"].get("judge")]
            if judged:
                out["judge_ok"] = _mean([1.0 if j else 0.0 for j in judged])
            out["cites_source"] = _mean([1.0 if r["answer"]["cited_expected_source"] else 0.0 for r in a_ans])
            out["correct_abstention"] = _mean([1.0 if r["answer"]["abstained"] else 0.0 for r in a_un])
            out["false_abstention"] = _mean([1.0 if r["answer"]["abstained"] else 0.0 for r in a_ans])
        return out

    by_cat: dict[str, list[dict]] = defaultdict(list)
    for r in results:
        by_cat[r["category"]].append(r)
    ans_scores = [r["retrieval"]["top_score"] for r in results if r["answerable"] and r["retrieval"]["top_score"] is not None]
    un_scores = [r["retrieval"]["top_score"] for r in results if not r["answerable"] and r["retrieval"]["top_score"] is not None]
    return {
        "overall": block(results),
        "by_category": {c: block(rows) for c, rows in sorted(by_cat.items())},
        "top1_score": {
            "answerable_median": statistics.median(ans_scores) if ans_scores else None,
            "answerable_min": min(ans_scores) if ans_scores else None,
            "unanswerable_median": statistics.median(un_scores) if un_scores else None,
            "unanswerable_max": max(un_scores) if un_scores else None,
        },
    }


# ---------- runner ----------

class EvalAborted(RuntimeError):
    """Raised when the LLM keeps failing, so a misconfiguration does not burn through every case."""


MAX_CONSECUTIVE_ERRORS = 3

def run_eval(cases: list[GoldenCase], retrieve_fn: Callable, ks: list[int],
             answer_fn: Callable | None = None, judge_fn: Callable | None = None) -> dict:
    results = []
    errors_in_a_row = 0
    for c in cases:
        passages = retrieve_fn(c.question, max(ks))
        row = {"id": c.id, "question": c.question, "category": c.category, "answerable": c.answerable,
               "retrieval": score_retrieval(c, passages)}
        if answer_fn is not None:
            try:
                row["answer"] = {"text": (text := answer_fn(c.question)), **score_answer(c, text)}
                errors_in_a_row = 0
                if judge_fn is not None and c.answerable:
                    try:
                        row["answer"]["judge"] = judge_fn(c, text)
                    except Exception as jexc:  # a flaky judge must not sink the run
                        row["answer"]["judge"] = None
                        row["answer"]["judge_error"] = str(jexc)
            except Exception as exc:  # LLM down, rate limit, ...
                errors_in_a_row += 1
                if errors_in_a_row >= MAX_CONSECUTIVE_ERRORS:
                    raise EvalAborted(f"{errors_in_a_row} LLM calls failed in a row; last error: {exc}") from exc
                row["answer"] = {"text": "", "error": str(exc), "abstained": False, "ok": False,
                                 "missing_keywords": list(c.must_include), "cited_expected_source": False}
        results.append(row)
    return {"results": results, "metrics": aggregate(results, ks)}


# ---------- reporting ----------

def _f(v) -> str:
    return "  -  " if v is None else f"{v:.2f}"


def format_report(report: dict, ks: list[int], meta: dict) -> str:
    m = report["metrics"]
    cols = [f"hit@{k}" for k in ks] + [f"prec@{max(ks)}", "mrr", "evidence_recall"]
    has_ans = "answer_ok" in m["overall"]
    if has_ans:
        if "judge_ok" in m["overall"]:
            cols += ["judge_ok"]
        cols += ["answer_ok", "cites_source", "correct_abstention", "false_abstention"]
    head = ["category", "n"] + [c.replace("evidence_recall", "ev.rec").replace("judge_ok", "judge").replace("correct_abstention", "abst✓")
                               .replace("false_abstention", "abst✗") for c in cols]
    lines = ["Config: " + ", ".join(f"{k}={v}" for k, v in meta.items()), ""]
    rows = [["ALL", m["overall"]["n"]] + [_f(m["overall"].get(c)) for c in cols]]
    rows += [[cat, b["n"]] + [_f(b.get(c)) for c in cols] for cat, b in m["by_category"].items()]
    widths = [max(len(str(x)) for x in col) for col in zip(head, *rows)]
    fmt = lambda r: "  ".join(str(x).ljust(w) for x, w in zip(r, widths))
    lines += [fmt(head), fmt(["-" * w for w in widths])] + [fmt(r) for r in rows]
    s = m["top1_score"]
    lines += ["", "Top-1 similarity (use it to pick a 'not in the notes' threshold):",
              f"  answerable   median {_f(s['answerable_median'])}  min {_f(s['answerable_min'])}",
              f"  unanswerable median {_f(s['unanswerable_median'])}  max {_f(s['unanswerable_max'])}"]
    misses = [r for r in report["results"] if r["answerable"] and not (r["retrieval"]["rank"] and r["retrieval"]["rank"] <= max(ks))]
    if misses:
        lines += ["", f"Retrieval misses (not in top {max(ks)}):"]
        lines += [f"  {r['id']} [{r['category']}] {r['question']}" for r in misses]
    late = [r for r in report["results"] if r["answerable"] and r["retrieval"]["rank"] and r["retrieval"]["rank"] > 1]
    if late:
        lines += ["", "Found, but not ranked first (rank, what ranked first):"]
        for r in late:
            top = r["retrieval"]["retrieved"][0]
            lines.append(f"  {r['id']} [{r['category']}] rank {r['retrieval']['rank']}, top was {top[0]} ({top[1]})  {r['question']}")
    wrong = [r for r in report["results"] if (r.get("answer") or {}).get("judge") and not r["answer"]["judge"]["correct"]]
    if wrong:
        lines += ["", "Judged incorrect:"]
        lines += [f"  {r['id']} [{r['category']}] {r['question']}  -> {r['answer']['judge']['reason']}" for r in wrong]
    bad = [r for r in report["results"] if "answer" in r and not r["answer"]["ok"]]
    if bad:
        lines += ["", "Answer failures:"]
        for r in bad:
            a = r["answer"]
            why = a.get("error") or ("should have abstained" if not r["answerable"] else
                                     "abstained" if a["abstained"] else f"missing {a.get('missing_keywords')}")
            lines.append(f"  {r['id']} [{r['category']}] {r['question']}  -> {why}")
    return "\n".join(lines)


def select_cases(cases: list[GoldenCase], ids: str | None) -> list[GoldenCase]:
    """Keep only the comma-separated ids (e.g. "q12,q28"); unknown ids are an error."""
    if not ids:
        return cases
    wanted = [i.strip() for i in ids.split(",") if i.strip()]
    known = {c.id for c in cases}
    unknown = [i for i in wanted if i not in known]
    if unknown:
        raise ValueError(f"unknown case id(s): {', '.join(unknown)}")
    return [c for c in cases if c.id in set(wanted)]


def write_json(path: str, data: dict) -> None:
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="python -m src.eval", description=__doc__.split("\n\n")[0])
    ap.add_argument("--golden", default="data/eval/golden.json")
    ap.add_argument("--ks", default="1,3,4", help="comma-separated k values; use the k the LLM sees (TOP_K, default 4) as the largest")
    ap.add_argument("--answers", action="store_true", help="also generate answers with the LLM")
    ap.add_argument("--judge", action="store_true",
                    help="grade answers with the LLM against the reference answer (needs --answers)")
    ap.add_argument("--only", metavar="IDS", help="run only these case ids, e.g. q12,q28")
    ap.add_argument("--json", metavar="PATH", help="write the full report as JSON")
    ap.add_argument("--min-hit", type=float, help="exit 1 if overall hit@max(k) is below this")
    args = ap.parse_args(argv)
    ks = sorted({int(x) for x in args.ks.split(",")})

    from . import config
    from .ingest import count_chunks, list_sources
    from .retriever import retrieve

    try:
        cases = select_cases(load_golden(args.golden), args.only)
    except ValueError as exc:
        ap.error(str(exc))
    n_chunks = count_chunks()
    if n_chunks == 0:
        print("The index is empty. Build it first: python -m src.ingest", file=sys.stderr)
        return 2
    wanted = {s for c in cases for s in c.expected_sources}
    missing = sorted(wanted - set(list_sources()))
    if missing:
        print(f"Warning: golden set cites notes that are not indexed: {missing}\n"
              "Run: python -m src.ingest\n", file=sys.stderr)

    if args.judge and not args.answers:
        ap.error("--judge needs --answers")
    answer_fn = judge_fn = None
    meta = {"embed_model": config.EMBED_MODEL, "chunk_size": config.CHUNK_SIZE,
            "overlap": config.CHUNK_OVERLAP, "retrieval": config.RETRIEVAL_MODE, "chunks": n_chunks, "cases": len(cases)}
    if args.answers:
        from .rag import answer_question
        answer_fn = lambda q: answer_question(q).text
        meta["llm"] = config.LLM_MODEL
        meta["top_k"] = config.TOP_K
        if args.judge:
            from .llm import chat
            judge_model = config.JUDGE_MODEL or config.LLM_MODEL
            judge_fn = make_llm_judge(lambda sys_, usr, temperature=0.0: chat(sys_, usr, temperature, model=judge_model))
            meta["judge"] = judge_model + ("" if config.JUDGE_MODEL else " (same model as the answerer)")

    try:
        report = run_eval(cases, lambda q, k: retrieve(q, top_k=k), ks, answer_fn, judge_fn)
    except EvalAborted as exc:
        print(f"Stopped: {exc}\nCheck LLM_BASE_URL / LLM_API_KEY / LLM_MODEL in .env "
              "(for Ollama: is `ollama serve` running and the model pulled?).", file=sys.stderr)
        return 2
    print(format_report(report, ks, meta))
    if args.json:
        write_json(args.json, {"config": meta, **report})
        print(f"\nFull report written to {args.json}")
    if args.min_hit is not None:
        hit = report["metrics"]["overall"][f"hit@{max(ks)}"]
        if hit is None or hit < args.min_hit:
            print(f"\nFAIL: hit@{max(ks)} = {hit} < {args.min_hit}", file=sys.stderr)
            return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
