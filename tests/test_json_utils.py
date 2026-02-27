import unittest
from unittest.mock import patch

from pydantic import BaseModel

from sena.agent.utils.json_utils import call_llm_with_format, safe_parse_json


class _Schema(BaseModel):
    name: str


class TestSafeParseJson(unittest.TestCase):
    def test_returns_dict_as_is(self):
        # Verifies dictionaries pass through unchanged.
        self.assertEqual(safe_parse_json({"a": 1}), {"a": 1})

    def test_parses_valid_json_string(self):
        # Verifies valid JSON object strings are parsed to dict.
        self.assertEqual(safe_parse_json('{"a": 1}'), {"a": 1})

    def test_invalid_json_returns_empty_dict(self):
        # Verifies invalid JSON safely falls back to an empty dict.
        self.assertEqual(safe_parse_json("not-json"), {})

    def test_non_dict_json_returns_empty_dict(self):
        # Verifies non-object JSON payloads are rejected.
        self.assertEqual(safe_parse_json('[1,2,3]'), {})


class TestCallLlmWithFormat(unittest.TestCase):
    @patch("sena.agent.utils.json_utils.ollama.chat")
    def test_returns_validated_model(self, chat_mock):
        # Verifies structured LLM output is validated into the schema model.
        chat_mock.return_value = {"message": {"content": '{"name":"Zen"}'}}

        result = call_llm_with_format(
            model="qwen",
            messages=[{"role": "user", "content": "hi"}],
            schema_class=_Schema,
        )

        self.assertIsNotNone(result)
        self.assertEqual(result.name, "Zen")

    @patch("sena.agent.utils.json_utils.ollama.chat")
    def test_validation_failure_returns_none(self, chat_mock):
        # Verifies invalid structured output returns None instead of crashing.
        chat_mock.return_value = {"message": {"content": '{"wrong":"field"}'}}

        result = call_llm_with_format(
            model="qwen",
            messages=[{"role": "user", "content": "hi"}],
            schema_class=_Schema,
        )

        self.assertIsNone(result)
