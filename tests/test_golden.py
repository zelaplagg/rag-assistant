import collections
import unittest

from src.golden import contains_evidence, load_golden, validate


class GoldenSetTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.cases = load_golden()

    def test_dataset_matches_notes(self):
        self.assertEqual(validate(self.cases), [])

    def test_has_every_kind_of_case(self):
        cats = collections.Counter(c.category for c in self.cases)
        for needed in ("factual", "paraphrase", "multi_doc", "cross_lingual", "unanswerable"):
            self.assertGreaterEqual(cats[needed], 3, needed)

    def test_unanswerable_share_is_reasonable(self):
        share = sum(not c.answerable for c in self.cases) / len(self.cases)
        self.assertTrue(0.1 <= share <= 0.4, share)

    def test_evidence_matching_ignores_markdown_and_line_breaks(self):
        chunk = "- **FD004:** six operating conditions, two fault modes\n  (the hardest subset)."
        self.assertTrue(contains_evidence(chunk, "two fault modes (the hardest subset)"))
        self.assertFalse(contains_evidence(chunk, "the easiest subset"))

    def test_validator_catches_a_broken_case(self):
        bad = load_golden()[0]
        bad.evidence = ["this sentence is not in the notes"]
        self.assertTrue(any("evidence not found" in p for p in validate([bad])))


if __name__ == "__main__":
    unittest.main()
