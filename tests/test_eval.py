import unittest
from dataclasses import dataclass

from src.eval import make_llm_judge, parse_judge, aggregate, format_report, is_abstention, run_eval, score_answer, score_retrieval
from src.golden import GoldenCase


@dataclass
class P:
    text: str
    source: str
    score: float


def case(**kw):
    base = dict(id="q1", question="?", category="factual", lang="en", answerable=True,
                expected_sources=["a.md"], evidence=["the answer"], reference_answer="", must_include=["answer"])
    base.update(kw)
    return GoldenCase(**base)


class RetrievalScoreTests(unittest.TestCase):
    def test_rank_is_position_of_first_relevant_chunk(self):
        ps = [P("noise", "a.md", .9), P("here is THE   answer", "a.md", .8)]
        self.assertEqual(score_retrieval(case(), ps)["rank"], 2)

    def test_right_text_from_wrong_source_is_not_relevant(self):
        self.assertIsNone(score_retrieval(case(), [P("the answer", "b.md", .9)])["rank"])

    def test_evidence_recall_counts_phrases_across_chunks(self):
        c = case(evidence=["alpha", "beta", "gamma"])
        r = score_retrieval(c, [P("alpha", "a.md", .9), P("beta", "a.md", .8)])
        self.assertAlmostEqual(r["evidence_recall"], 2 / 3)

    def test_no_passages(self):
        r = score_retrieval(case(), [])
        self.assertIsNone(r["rank"])
        self.assertIsNone(r["top_score"])


class AnswerScoreTests(unittest.TestCase):
    def test_abstention_detection(self):
        self.assertTrue(is_abstention("The notes do not contain this information."))
        self.assertTrue(is_abstention("У нотатках цього немає."))
        self.assertFalse(is_abstention("FD004 is the hardest subset [cmapss_dataset.md]."))

    def test_answerable_needs_keywords_and_no_abstention(self):
        c = case(must_include=["fd004"], expected_sources=["a.md"])
        ok = score_answer(c, "It is FD004 [a.md]")
        self.assertTrue(ok["ok"] and ok["cited_expected_source"])
        self.assertFalse(score_answer(c, "It is FD003")["ok"])
        self.assertFalse(score_answer(c, "The notes do not contain FD004")["ok"])

    def test_unanswerable_must_abstain(self):
        c = case(answerable=False, expected_sources=[], evidence=[], must_include=[])
        self.assertTrue(score_answer(c, "I can't find that in your notes.")["ok"])
        self.assertFalse(score_answer(c, "Vienna.")["ok"])


class JudgeParsingTests(unittest.TestCase):
    def test_plain_and_fenced_json(self):
        self.assertTrue(parse_judge('{"correct": true, "reason": "ok"}')["correct"])
        self.assertFalse(parse_judge('```json\n{"correct": false, "reason": "wrong"}\n```')["correct"])

    def test_garbage_raises(self):
        with self.assertRaises(ValueError):
            parse_judge("I think it is fine")
        with self.assertRaises(ValueError):
            parse_judge('{"correct": "yes"}')

    def test_llm_judge_sends_reference_and_candidate(self):
        seen = {}
        def fake_chat(system, prompt, temperature=0.1):
            seen.update(system=system, prompt=prompt, t=temperature)
            return '{"correct": true, "reason": "ok"}'
        out = make_llm_judge(fake_chat)(case(reference_answer="REF"), "CAND")
        self.assertTrue(out["correct"])
        self.assertIn("REF", seen["prompt"])
        self.assertIn("CAND", seen["prompt"])
        self.assertEqual(seen["t"], 0.0)


class RunnerTests(unittest.TestCase):
    def setUp(self):
        self.cases = [case(id="q1"), case(id="q2"),
                      case(id="q3", category="unanswerable", answerable=False, expected_sources=[], evidence=[], must_include=[])]
        self.index = {
            "q1": [P("the answer", "a.md", .9), P("x", "a.md", .5)],
            "q2": [P("x", "a.md", .7), P("y", "a.md", .6), P("the answer", "a.md", .5)],
            "q3": [P("x", "a.md", .3)],
        }

    def run_it(self, answer_fn=None, judge_fn=None):
        # distinct questions per case so the fake retriever can tell them apart
        for c in self.cases:
            c.question = c.id
        return run_eval(self.cases, lambda q, k: self.index[q][:k], [1, 3], answer_fn, judge_fn)

    def test_metrics(self):
        m = self.run_it()["metrics"]["overall"]
        self.assertEqual(m["n"], 3)
        self.assertEqual(m["n_answerable"], 2)
        self.assertAlmostEqual(m["hit@1"], 0.5)
        self.assertAlmostEqual(m["hit@3"], 1.0)
        self.assertAlmostEqual(m["mrr"], (1 + 1 / 3) / 2)

    def test_top1_scores_separate_answerable_from_unanswerable(self):
        s = self.run_it()["metrics"]["top1_score"]
        self.assertAlmostEqual(s["answerable_min"], .7)
        self.assertAlmostEqual(s["unanswerable_max"], .3)

    def test_answer_mode_and_llm_errors_do_not_crash(self):
        def fake(q):
            if q == "q2":
                raise RuntimeError("llm down")
            return "the answer" if q == "q1" else "I can't find that."
        rep = self.run_it(fake)
        m = rep["metrics"]["overall"]
        self.assertAlmostEqual(m["answer_ok"], 0.5)
        self.assertAlmostEqual(m["correct_abstention"], 1.0)
        text = format_report(rep, [1, 3], {"embed_model": "x"})
        self.assertIn("llm down", text)
        self.assertIn("Answer failures", text)
        self.assertIn("not ranked first", text)  # q2 is found at rank 3
        self.assertNotIn("Retrieval misses", text)  # everything is found within k=3

    def test_aborts_after_consecutive_llm_errors(self):
        from src.eval import EvalAborted
        calls = []
        def broken(q):
            calls.append(q)
            raise RuntimeError("401 bad key")
        with self.assertRaises(EvalAborted):
            self.run_it(broken)
        self.assertEqual(len(calls), 3)

    def test_json_report_creates_missing_folder(self):
        import json, os, tempfile
        from src.eval import write_json
        out = os.path.join(tempfile.mkdtemp(), "reports", "r.json")
        write_json(out, {"a": "Привіт"})
        with open(out, encoding="utf-8") as f:
            self.assertEqual(json.load(f), {"a": "Привіт"})

    def test_judge_scores_are_aggregated_and_reported(self):
        judge = lambda c, a: {"correct": c.id == "q1", "reason": "nope"}
        rep = self.run_it(lambda q: "the answer" if q != "q3" else "I can't find that.", judge)
        self.assertAlmostEqual(rep["metrics"]["overall"]["judge_ok"], 0.5)
        text = format_report(rep, [1, 3], {})
        self.assertIn("judge", text)
        self.assertIn("Judged incorrect", text)

    def test_judge_failure_does_not_abort_run(self):
        def bad_judge(c, a):
            raise ValueError("not json")
        rep = self.run_it(lambda q: "the answer", bad_judge)
        self.assertNotIn("judge_ok", rep["metrics"]["overall"])
        self.assertIn("judge_error", rep["results"][0]["answer"])

    def test_by_category_breakdown(self):
        self.assertIn("unanswerable", self.run_it()["metrics"]["by_category"])


if __name__ == "__main__":
    unittest.main()
