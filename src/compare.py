"""Compare chunking x retrieval configurations on the golden set (retrieval only: no LLM, free).

    python -m src.compare

Each chunking mode is indexed into a temporary directory, so your real index is not touched.
"""
from __future__ import annotations

import argparse
import shutil
import sys
import tempfile

from .eval import run_eval
from .golden import load_golden

CHUNKING_MODES = ("char", "heading")
RETRIEVAL_MODES = ("vector", "hybrid")
COLUMNS = ("hit@1", "hit@3", "hit@4", "prec@4", "mrr", "evidence_recall")


def format_comparison(rows: list[dict]) -> str:
    head = ["chunking", "retrieval", "chunks"] + [c.replace("evidence_recall", "ev.rec") for c in COLUMNS]
    body = [[r["chunking"], r["retrieval"], str(r["chunks"])] +
            ["-" if r["metrics"].get(c) is None else f"{r['metrics'][c]:.2f}" for c in COLUMNS] for r in rows]
    widths = [max(len(x) for x in col) for col in zip(head, *body)]
    fmt = lambda r: "  ".join(x.ljust(w) for x, w in zip(r, widths))
    best = max(rows, key=lambda r: (r["metrics"].get("hit@1") or 0, r["metrics"].get("prec@4") or 0))
    return "\n".join([fmt(head), fmt(["-" * w for w in widths])] + [fmt(b) for b in body] +
                     ["", f"Best by hit@1 then prec@4: chunking={best['chunking']}, retrieval={best['retrieval']}"])


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="python -m src.compare", description=__doc__.split("\n\n")[0])
    ap.add_argument("--golden", default="data/eval/golden.json")
    args = ap.parse_args(argv)

    from . import config, ingest
    from .retriever import retrieve

    cases = load_golden(args.golden)
    saved = (config.CHROMA_DIR, config.CHUNKING, config.RETRIEVAL_MODE)
    rows = []
    tmp = tempfile.mkdtemp(prefix="studymate-compare-")
    try:
        for chunking in CHUNKING_MODES:
            config.CHROMA_DIR = f"{tmp}/{chunking}"
            config.CHUNKING = chunking
            n_chunks = ingest.build_index()
            for mode in RETRIEVAL_MODES:
                config.RETRIEVAL_MODE = mode
                report = run_eval(cases, lambda q, k: retrieve(q, top_k=k), [1, 3, 4])
                rows.append({"chunking": chunking, "retrieval": mode, "chunks": n_chunks,
                             "metrics": report["metrics"]["overall"]})
    finally:
        config.CHROMA_DIR, config.CHUNKING, config.RETRIEVAL_MODE = saved
        shutil.rmtree(tmp, ignore_errors=True)
    print(format_comparison(rows))
    return 0


if __name__ == "__main__":
    sys.exit(main())
