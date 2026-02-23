import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from zenbot.agent.config import _parse_bool, load_settings


class TestParseBool(unittest.TestCase):
    def test_parse_bool_true_variants(self):
        # Verifies that common truthy values are parsed as True.
        for value in ["true", "TRUE", "1", "yes", True]:
            with self.subTest(value=value):
                self.assertTrue(_parse_bool(value))

    def test_parse_bool_false_variants(self):
        # Verifies that common falsy values are parsed as False.
        for value in ["false", "FALSE", "0", "no", False]:
            with self.subTest(value=value):
                self.assertFalse(_parse_bool(value))

    def test_parse_bool_invalid_raises(self):
        # Verifies that invalid boolean text raises a ValueError.
        with self.assertRaises(ValueError):
            _parse_bool("maybe")


class TestLoadSettings(unittest.TestCase):
    def _write_toml(self, directory: Path, name: str, content: str) -> None:
        (directory / name).write_text(content, encoding="utf-8")

    def test_load_settings_from_default_toml(self):
        # Verifies settings are loaded correctly from default TOML values.
        with tempfile.TemporaryDirectory() as tmp:
            config_dir = Path(tmp)
            self._write_toml(
                config_dir,
                "default.toml",
                """
[llm]
model = "qwen2.5:3b"
stream = true
think = false

[agent]
max_internal_steps = 8
max_history_messages = 20
debug = false
reminder_poll_seconds = 30
""".strip(),
            )

            with patch("zenbot.agent.config._get_config_dir", return_value=config_dir):
                settings = load_settings()

            self.assertEqual(settings.llm.model, "qwen2.5:3b")
            self.assertTrue(settings.llm.stream)
            self.assertFalse(settings.llm.think)
            self.assertEqual(settings.agent.max_internal_steps, 8)
            self.assertEqual(settings.agent.max_history_messages, 20)
            self.assertFalse(settings.agent.debug)
            self.assertEqual(settings.agent.reminder_poll_seconds, 30)

    def test_env_overrides_toml(self):
        # Verifies environment variables override values from TOML config.
        with tempfile.TemporaryDirectory() as tmp:
            config_dir = Path(tmp)
            self._write_toml(
                config_dir,
                "default.toml",
                """
[llm]
model = "default-model"
stream = false
think = false

[agent]
max_internal_steps = 3
max_history_messages = 5
debug = false
reminder_poll_seconds = 30
""".strip(),
            )

            env = {
                "ZENBOT_MODEL": "env-model",
                "ZENBOT_STREAM": "true",
                "ZENBOT_THINK": "true",
                "ZENBOT_MAX_INTERNAL_STEPS": "12",
                "ZENBOT_MAX_HISTORY_MESSAGES": "30",
                "ZENBOT_REMINDER_POLL_SECONDS": "15",
                "ZENBOT_DEBUG": "true",
            }

            with patch("zenbot.agent.config._get_config_dir", return_value=config_dir), patch.dict(os.environ, env, clear=False):
                settings = load_settings()

            self.assertEqual(settings.llm.model, "env-model")
            self.assertTrue(settings.llm.stream)
            self.assertTrue(settings.llm.think)
            self.assertEqual(settings.agent.max_internal_steps, 12)
            self.assertEqual(settings.agent.max_history_messages, 30)
            self.assertEqual(settings.agent.reminder_poll_seconds, 15)
            self.assertTrue(settings.agent.debug)

    def test_invalid_max_internal_steps_raises(self):
        # Verifies validation fails when max_internal_steps is zero.
        with tempfile.TemporaryDirectory() as tmp:
            config_dir = Path(tmp)
            self._write_toml(
                config_dir,
                "default.toml",
                """
[llm]
model = "m"
stream = true
think = false

[agent]
max_internal_steps = 0
max_history_messages = 10
debug = false
reminder_poll_seconds = 30
""".strip(),
            )

            with patch("zenbot.agent.config._get_config_dir", return_value=config_dir):
                with self.assertRaises(ValueError):
                    load_settings()

    def test_invalid_debug_env_raises(self):
        # Verifies invalid debug env values are rejected.
        with tempfile.TemporaryDirectory() as tmp:
            config_dir = Path(tmp)
            self._write_toml(
                config_dir,
                "default.toml",
                """
[llm]
model = "m"
stream = true
think = false

[agent]
max_internal_steps = 2
max_history_messages = 10
debug = false
reminder_poll_seconds = 30
""".strip(),
            )

            with patch("zenbot.agent.config._get_config_dir", return_value=config_dir), patch.dict(
                os.environ,
                {"ZENBOT_DEBUG": "notabool"},
                clear=False,
            ):
                with self.assertRaises(ValueError):
                    load_settings()

    def test_invalid_reminder_poll_seconds_raises(self):
        # Verifies reminder polling interval must be > 0.
        with tempfile.TemporaryDirectory() as tmp:
            config_dir = Path(tmp)
            self._write_toml(
                config_dir,
                "default.toml",
                """
[llm]
model = "m"
stream = true
think = false

[agent]
max_internal_steps = 2
max_history_messages = 10
debug = false
reminder_poll_seconds = 0
""".strip(),
            )

            with patch("zenbot.agent.config._get_config_dir", return_value=config_dir):
                with self.assertRaises(ValueError):
                    load_settings()
