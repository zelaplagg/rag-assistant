import unittest


class PromptTests(unittest.TestCase):
    def test_qa_prompt_asks_for_real_file_names_not_a_placeholder(self):
        try:
            from src.rag import QA_SYSTEM
        except ImportError:
            self.skipTest("dependencies not installed")
        # The model copied the literal example "[source]" into its answers; never reintroduce it.
        self.assertNotIn("[source]", QA_SYSTEM)
        self.assertIn("file name", QA_SYSTEM)

    def test_qa_prompt_marks_notes_as_untrusted(self):
        try:
            from src.rag import QA_SYSTEM
        except ImportError:
            self.skipTest("dependencies not installed")
        self.assertIn("untrusted", QA_SYSTEM)


if __name__ == "__main__":
    unittest.main()
