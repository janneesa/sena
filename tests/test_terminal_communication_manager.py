import unittest
from types import SimpleNamespace
from unittest.mock import call, patch

from zenbot.agent.types import EventType
from zenbot.agent.workers.terminal_communication_manager import BUSY_MESSAGE, TerminalCommunicationManager


class TestTerminalCommunicationManager(unittest.TestCase):
    @patch("builtins.input", return_value="hello")
    def test_read_input_tracks_active_prompt(self, input_mock):
        manager = TerminalCommunicationManager()

        value = manager._read_input("> ")

        self.assertEqual(value, "hello")
        self.assertFalse(manager._input_active)
        self.assertEqual(manager._input_prompt, "> ")
        input_mock.assert_called_once_with("> ")

    @patch("builtins.print")
    def test_emit_text_renders_prompt_when_input_active(self, print_mock):
        manager = TerminalCommunicationManager()
        manager._input_active = True
        manager._input_prompt = "> "

        manager.emit_text("Hi")

        print_mock.assert_has_calls(
            [
                call(),
                call("Hi"),
                call("> ", end="", flush=True),
            ]
        )

    @patch("builtins.print")
    def test_busy_agent_emits_busy_message_and_queues_input(self, _print_mock):
        manager = TerminalCommunicationManager()
        queued = []
        manager._agent = SimpleNamespace(
            state=SimpleNamespace(name="GENERATE"),
            has_queued_events=lambda: False,
            enqueue_event=queued.append,
        )

        manager._handle_user_message("hello")

        self.assertEqual(len(queued), 1)
        self.assertEqual(queued[0].event_type, EventType.USER_MESSAGE)
        self.assertEqual(queued[0].payload, "hello")
        _print_mock.assert_any_call(BUSY_MESSAGE)

    @patch("builtins.print")
    def test_idle_agent_queues_without_busy_message(self, print_mock):
        manager = TerminalCommunicationManager()
        queued = []
        manager._agent = SimpleNamespace(
            state=SimpleNamespace(name="IDLE"),
            has_queued_events=lambda: False,
            enqueue_event=queued.append,
        )

        manager._handle_user_message("hello")

        self.assertEqual(len(queued), 1)
        print_mock.assert_not_called()

    @patch("builtins.print")
    def test_busy_due_to_nonempty_queue_emits_busy_message(self, print_mock):
        manager = TerminalCommunicationManager()
        queued = []
        manager._agent = SimpleNamespace(
            state=SimpleNamespace(name="IDLE"),
            has_queued_events=lambda: True,
            enqueue_event=queued.append,
        )

        manager._handle_user_message("hello")

        self.assertEqual(len(queued), 1)
        print_mock.assert_any_call(BUSY_MESSAGE)


if __name__ == "__main__":
    unittest.main()
