import unittest

from src.hybrid import BM25, rrf, tokenize

DOCS = [
    "Retrieval-Augmented Generation improves answers of a language model with external passages.",
    "Top-k: the number of passages retrieved for each question.",
    "FD001 has one operating condition and one fault mode.",
]


class TokenizeTests(unittest.TestCase):
    def test_lowercase_split_and_stopwords(self):
        self.assertEqual(tokenize("What is Top-k?"), ["top", "k"])

    def test_non_latin_tokens_survive(self):
        self.assertEqual(tokenize("Що таке RAG"), ["що", "таке", "rag"])


class BM25Tests(unittest.TestCase):
    def test_exact_term_ranks_first(self):
        self.assertEqual(BM25(DOCS).rank("What is top-k?")[0], 1)

    def test_rare_term_beats_common_one(self):
        self.assertEqual(BM25(DOCS).rank("FD001 passages")[0], 2)

    def test_no_overlap_means_no_hits(self):
        self.assertEqual(BM25(DOCS).rank("quantum chromodynamics"), [])

    def test_empty_corpus(self):
        self.assertEqual(BM25([]).rank("anything"), [])


class RrfTests(unittest.TestCase):
    def test_items_found_by_both_rankings_rise(self):
        self.assertEqual(rrf([["a", "b", "c"], ["c", "d"]])[0], "c")

    def test_keyword_only_hit_is_kept(self):
        self.assertIn("d", rrf([["a", "b"], ["d"]]))

    def test_deterministic_ties(self):
        self.assertEqual(rrf([["b"], ["a"]]), ["a", "b"])


if __name__ == "__main__":
    unittest.main()
