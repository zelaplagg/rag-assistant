import unittest

from src.compare import format_comparison


def row(chunking, retrieval, hit1, prec):
    return {"chunking": chunking, "retrieval": retrieval, "chunks": 10,
            "metrics": {"hit@1": hit1, "hit@3": .9, "hit@4": .9, "prec@4": prec, "mrr": .8, "evidence_recall": None}}


class FormatTests(unittest.TestCase):
    def test_table_and_best_pick(self):
        text = format_comparison([row("char", "vector", .7, .3), row("heading", "hybrid", .9, .4)])
        self.assertIn("heading", text)
        self.assertIn("Best by hit@1 then prec@4: chunking=heading, retrieval=hybrid", text)
        self.assertIn(" -", text)  # missing metric shown as a dash

    def test_ties_on_hit1_are_broken_by_precision(self):
        text = format_comparison([row("char", "vector", .8, .2), row("char", "hybrid", .8, .5)])
        self.assertIn("retrieval=hybrid", text)


if __name__ == "__main__":
    unittest.main()
