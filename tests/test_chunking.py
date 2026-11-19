import os
import unittest

from src.chunking import _blocks, chunk_markdown, split_sections

DOC = """# Notes

Intro paragraph.

## Types

- **Supervised:** learns from labels.
- **Reinforcement learning:** an agent learns by trial and error,
  receiving rewards.

### Deep dive

Details here.

## Metrics

Accuracy is a share.
"""


class SectionTests(unittest.TestCase):
    def test_heading_paths(self):
        paths = [p for p, _ in split_sections(DOC)]
        self.assertEqual(paths, [["Notes"], ["Notes", "Types"], ["Notes", "Types", "Deep dive"], ["Notes", "Metrics"]])

    def test_headings_inside_code_fences_are_text(self):
        secs = split_sections("# A\n\n```\n# not a heading\n```\n")
        self.assertEqual(len(secs), 1)
        self.assertIn("# not a heading", secs[0][1])

    def test_no_headings(self):
        self.assertEqual(split_sections("just text\n\nmore"), [([], "just text\n\nmore")])


class ChunkTests(unittest.TestCase):
    def test_each_chunk_starts_with_its_heading_path(self):
        chunks = chunk_markdown(DOC, 800)
        self.assertEqual(len(chunks), 4)
        self.assertTrue(chunks[1].startswith("Notes > Types\n\n"))
        self.assertIn("Reinforcement learning", chunks[1])

    def test_label_and_sentence_stay_together(self):
        c = [c for c in chunk_markdown(DOC, 800) if "trial and error" in c]
        self.assertEqual(len(c), 1)
        self.assertIn("**Reinforcement learning:** an agent learns by trial and error,\n  receiving rewards.", c[0])

    def test_long_section_splits_between_items_not_inside(self):
        items = "\n".join(f"- item {i}: " + "word " * 12 for i in range(12))
        chunks = chunk_markdown("## List\n\n" + items, 300)
        self.assertGreater(len(chunks), 1)
        for c in chunks:
            self.assertTrue(c.startswith("List\n\n"))
            self.assertLessEqual(len(c), 300)
            for line in c.splitlines()[2:]:
                self.assertTrue(line.startswith("- item"), line)  # no cut-off fragments

    def test_single_huge_paragraph_is_still_split(self):
        text = "## Big\n\n" + ("This is a sentence. " * 200)
        chunks = chunk_markdown(text, 400)
        self.assertGreater(len(chunks), 5)
        self.assertTrue(all(len(c) <= 400 for c in chunks))

    def test_no_text_is_lost(self):
        words = set(DOC.replace("#", " ").replace("-", " ").replace("*", " ").split())
        joined = " ".join(chunk_markdown(DOC, 120))
        self.assertTrue(words <= set(joined.replace("*", " ").split()), words - set(joined.split()))

    def test_empty_and_heading_only(self):
        self.assertEqual(chunk_markdown("   ", 800), [])
        self.assertEqual(chunk_markdown("# Only a title\n", 800), [])

    def test_text_without_headings_has_no_prefix(self):
        self.assertEqual(chunk_markdown("plain note about RAG", 800), ["plain note about RAG"])

    def test_blocks_split_list_items(self):
        self.assertEqual(_blocks("para\n- a\n- b\n  cont"), ["para", "- a", "- b\n  cont"])


class RealNotesTests(unittest.TestCase):
    def test_sample_notes_give_self_contained_chunks(self):
        path = os.path.join("data", "docs", "lecture_ml_basics.md")
        with open(path, encoding="utf-8") as f:
            chunks = chunk_markdown(f.read(), 800)
        rl = [c for c in chunks if "trial and error" in c]
        self.assertEqual(len(rl), 1)
        self.assertIn("Reinforcement learning", rl[0])
        self.assertIn("Types of learning", rl[0])
        self.assertTrue(all(c.startswith("Lecture Notes: Machine Learning Basics") for c in chunks))


if __name__ == "__main__":
    unittest.main()
