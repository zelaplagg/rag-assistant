import types
import unittest

import sys

try:
    import openai  # noqa: F401
except ImportError:  # keep the tests runnable without the SDK: llm.py only needs the OpenAI name
    sys.modules["openai"] = types.SimpleNamespace(OpenAI=object)

try:
    import dotenv  # noqa: F401
except ImportError:
    sys.modules["dotenv"] = types.SimpleNamespace(load_dotenv=lambda *a, **k: None)

from src import llm


class Rejected(Exception):
    status_code = 400


def fake_client(calls, reject_temperature):
    def create(**kw):
        calls.append(kw)
        if reject_temperature and "temperature" in kw:
            raise Rejected("Unsupported value: 'temperature' does not support 0.1 with this model.")
        msg = types.SimpleNamespace(content="  hi  ")
        return types.SimpleNamespace(choices=[types.SimpleNamespace(message=msg)])
    return types.SimpleNamespace(chat=types.SimpleNamespace(completions=types.SimpleNamespace(create=create)))


class ChatTests(unittest.TestCase):
    def setUp(self):
        self.saved = (llm._client, set(llm._no_temperature))
        llm._no_temperature.clear()

    def tearDown(self):
        llm._client = self.saved[0]
        llm._no_temperature.clear()
        llm._no_temperature.update(self.saved[1])

    def test_normal_call_sends_temperature_and_strips(self):
        calls = []
        llm._client = fake_client(calls, False)
        self.assertEqual(llm.chat("s", "u", 0.3, model="m1"), "hi")
        self.assertEqual(calls[0]["temperature"], 0.3)
        self.assertEqual(calls[0]["model"], "m1")

    def test_retries_without_temperature_and_remembers(self):
        calls = []
        llm._client = fake_client(calls, True)
        self.assertEqual(llm.chat("s", "u", model="strict"), "hi")
        self.assertEqual(len(calls), 2)
        self.assertNotIn("temperature", calls[1])
        llm.chat("s", "u", model="strict")
        self.assertEqual(len(calls), 3)  # remembered: no failing first attempt
        self.assertNotIn("temperature", calls[2])

    def test_other_errors_are_not_swallowed(self):
        def create(**kw):
            raise RuntimeError("boom")
        llm._client = types.SimpleNamespace(chat=types.SimpleNamespace(completions=types.SimpleNamespace(create=create)))
        with self.assertRaises(RuntimeError):
            llm.chat("s", "u")


if __name__ == "__main__":
    unittest.main()
