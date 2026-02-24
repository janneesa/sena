import tempfile
import threading
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import zenbot.__main__ as app_main
from zenbot.agent.context import load_system_message
from zenbot.agent.types import Event, EventType


class TestContextBuilder(unittest.TestCase):
    def test_missing_files_return_fallback(self):
        # Verifies a safe default system prompt is returned when files are missing.
        with tempfile.TemporaryDirectory() as tmp:
            override = Path(tmp) / "system.md"
            self.assertEqual(load_system_message(override), "You are a helpful AI assistant.")

    def test_default_used_when_override_missing(self):
        # Verifies default_system.md is used when override is missing.
        with tempfile.TemporaryDirectory() as tmp:
            default_path = Path(tmp) / "default_system.md"
            default_path.write_text("default content", encoding="utf-8")
            override = Path(tmp) / "system.md"
            self.assertEqual(load_system_message(override), "default content")

    def test_override_used_when_nonempty(self):
        # Verifies system.md overrides default_system.md when non-empty.
        with tempfile.TemporaryDirectory() as tmp:
            default_path = Path(tmp) / "default_system.md"
            default_path.write_text("default content", encoding="utf-8")
            override = Path(tmp) / "system.md"
            override.write_text("override content", encoding="utf-8")
            self.assertEqual(load_system_message(override), "override content")

    def test_empty_override_uses_default(self):
        # Verifies empty override falls back to default.
        with tempfile.TemporaryDirectory() as tmp:
            default_path = Path(tmp) / "default_system.md"
            default_path.write_text("default content", encoding="utf-8")
            override = Path(tmp) / "system.md"
            override.write_text("\n\n", encoding="utf-8")
            self.assertEqual(load_system_message(override), "default content")


class TestMain(unittest.TestCase):
    @patch("zenbot.__main__.Agent")
    @patch("zenbot.__main__.ReminderWorker")
    @patch("zenbot.__main__.DatabaseHelper")
    @patch("zenbot.__main__.load_settings")
    def test_main_dispatches_user_event(
        self,
        load_settings_mock,
        _db_cls_mock,
        worker_cls_mock,
        agent_cls_mock,
    ):
        # Verifies main loop routes user input through queued event processing.
        load_settings_mock.return_value = SimpleNamespace(
            agent=SimpleNamespace(reminder_poll_seconds=30)
        )
        agent_instance = MagicMock()
        agent_cls_mock.return_value = agent_instance
        worker_instance = MagicMock()
        worker_cls_mock.return_value = worker_instance
        preset_stop_event = threading.Event()
        preset_stop_event.set()

        with patch("zenbot.__main__.threading.Event", return_value=preset_stop_event):
            with (
                patch.object(app_main.terminal_communication_manager, "start") as start_mock,
                patch.object(app_main.terminal_communication_manager, "stop") as stop_mock,
                patch.object(app_main.terminal_communication_manager, "emit_text") as emit_text_mock,
            ):
                def start_side_effect(agent, stop_event):
                    _ = stop_event
                    agent.enqueue_event(Event(event_type=EventType.USER_MESSAGE, payload="hello"))

                start_mock.side_effect = start_side_effect

                app_main.main()

                start_mock.assert_called_once()
                stop_mock.assert_called_once()
                emit_text_mock.assert_any_call("ZenBot (type 'exit' to quit)")

        self.assertEqual(agent_instance.enqueue_event.call_count, 1)
        event = agent_instance.enqueue_event.call_args[0][0]
        self.assertEqual(event.event_type, EventType.USER_MESSAGE)
        self.assertEqual(event.payload, "hello")
        self.assertGreaterEqual(agent_instance.process_queued_events.call_count, 1)
        worker_instance.start.assert_called_once()
        worker_instance.stop.assert_called_once()

    @patch("zenbot.__main__.load_settings", side_effect=RuntimeError("bad config"))
    def test_main_prints_config_error(self, _load_settings_mock):
        # Verifies configuration failures are shown to the user.
        with patch.object(app_main.terminal_communication_manager, "emit_text") as emit_text_mock:
            app_main.main()
        emit_text_mock.assert_any_call("Configuration error: bad config")
