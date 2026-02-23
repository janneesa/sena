import unittest
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from zenbot.agent.states.cleanup import Cleanup
from zenbot.agent.states.generate import Generate
from zenbot.agent.states.idle import Idle
from zenbot.agent.states.task import Task
from zenbot.agent.states.tools import UseTools
from zenbot.agent.types import Event, EventType, Turn


def _fake_agent(stream: bool = False) -> SimpleNamespace:
    output = MagicMock()
    toolbox = MagicMock()
    toolbox.get_ollama_tool_functions.return_value = []
    settings = SimpleNamespace(
        llm=SimpleNamespace(model="qwen", stream=stream, think=False),
        agent=SimpleNamespace(max_internal_steps=5),
    )
    return SimpleNamespace(
        settings=settings,
        output=output,
        toolbox=toolbox,
        messages=[{"role": "system", "content": "sys"}],
        turn=Turn(user_text="hello"),
        commit_turn=MagicMock(),
    )


class TestIdleState(unittest.TestCase):
    def test_ignores_non_user_message(self):
        # Verifies Idle state does not transition on internal tick events.
        agent = _fake_agent()
        state = Idle()
        next_state = state.handle(agent, Event(EventType.TICK))
        self.assertIs(next_state, state)

    def test_transitions_to_generate_on_user_message(self):
        # Verifies Idle captures user text and moves to Generate.
        agent = _fake_agent()
        state = Idle()
        next_state = state.handle(agent, Event(EventType.USER_MESSAGE, " hi "))
        self.assertIsInstance(next_state, Generate)
        self.assertEqual(agent.turn.user_text, "hi")

    def test_transitions_to_task_on_reminder_due(self):
        # Verifies Idle stores reminder payload and moves to Task.
        agent = _fake_agent()
        state = Idle()
        next_state = state.handle(
            agent,
            Event(EventType.REMINDER_DUE, {"task": "drink water", "notes": "right now"}),
        )
        self.assertIsInstance(next_state, Task)
        self.assertEqual(agent.turn.user_text, "")
        self.assertEqual(agent.turn.reminder_due_payload["task"], "drink water")


class TestCleanupState(unittest.TestCase):
    def test_tick_commits_and_returns_idle(self):
        # Verifies Cleanup commits the turn and returns to Idle.
        agent = _fake_agent()
        state = Cleanup()
        next_state = state.handle(agent, Event(EventType.TICK))
        agent.commit_turn.assert_called_once()
        self.assertIsInstance(next_state, Idle)


class TestGenerateState(unittest.TestCase):
    @patch("zenbot.agent.states.generate.ollama.chat")
    def test_no_tool_calls_sets_assistant_text_and_cleanup(self, chat_mock):
        # Verifies plain assistant responses go to Cleanup with emitted output.
        chat_mock.return_value = {"message": {"role": "assistant", "content": "Hello", "tool_calls": None}}
        agent = _fake_agent(stream=False)

        state = Generate()
        next_state = state.handle(agent, Event(EventType.TICK))

        self.assertIsInstance(next_state, Cleanup)
        self.assertEqual(agent.turn.assistant_text, "Hello")
        agent.output.emit_text.assert_called_once_with("Hello")

    @patch("zenbot.agent.states.generate.ollama.chat")
    def test_tool_calls_transition_to_use_tools(self, chat_mock):
        # Verifies tool-call responses queue calls and transition to UseTools.
        chat_mock.return_value = {
            "message": {
                "role": "assistant",
                "content": "",
                "tool_calls": [{"function": {"name": "datetime", "arguments": {}}}],
            }
        }
        agent = _fake_agent(stream=False)

        state = Generate()
        next_state = state.handle(agent, Event(EventType.TICK))

        self.assertIsInstance(next_state, UseTools)
        self.assertEqual(len(agent.turn.pending_tool_calls), 1)
        self.assertEqual(agent.turn.pending_tool_calls[0]["tool_name"], "datetime")


class TestUseToolsState(unittest.TestCase):
    def test_no_pending_calls_returns_generate(self):
        # Verifies UseTools returns to Generate when queue is empty.
        agent = _fake_agent()
        state = UseTools()
        next_state = state.handle(agent, Event(EventType.TICK))
        self.assertIsInstance(next_state, Generate)

    def test_executes_tool_and_returns_generate(self):
        # Verifies a queued tool call is executed and result is appended for LLM.
        agent = _fake_agent()
        agent.turn.pending_tool_calls = [{"tool_name": "datetime", "args": {}}]
        tool = SimpleNamespace(user_message="checking")
        agent.toolbox.get_tool.return_value = tool
        agent.toolbox.run_tool.return_value = {"ok": True}

        state = UseTools()
        next_state = state.handle(agent, Event(EventType.TICK))

        self.assertIsInstance(next_state, Generate)
        agent.output.emit_status.assert_called_once_with("checking")
        self.assertEqual(len(agent.turn.tool_results), 1)
        self.assertEqual(agent.turn.llm_messages[-1]["role"], "tool")

    def test_set_reminder_uses_direct_confirmation_and_cleanup(self):
        # Verifies set_reminder successful result is emitted directly without extra LLM paraphrasing.
        agent = _fake_agent()
        agent.turn.pending_tool_calls = [{"tool_name": "set_reminder", "args": {"request": "x"}}]
        tool = SimpleNamespace(user_message="Setting your reminder...")
        agent.toolbox.get_tool.return_value = tool
        agent.toolbox.run_tool.return_value = {
            "success": True,
            "confirmation": "Reminder set: go to bed on 19.02.2026 at 00:41.",
            "when": "2026-02-19T00:41:00+02:00",
        }

        state = UseTools()
        next_state = state.handle(agent, Event(EventType.TICK))

        self.assertIsInstance(next_state, Cleanup)
        agent.output.emit_text.assert_called_once_with(
            "Reminder set: go to bed on 19.02.2026 at 00:41."
        )
        self.assertEqual(
            agent.turn.assistant_text,
            "Reminder set: go to bed on 19.02.2026 at 00:41.",
        )


class TestTaskState(unittest.TestCase):
    @patch("zenbot.agent.states.task.ollama.chat")
    def test_reminder_due_generates_message(self, chat_mock):
        # Verifies Task generates a friendly reminder message.
        # (Reminder is already marked completed by the worker, not deleted here)
        chat_mock.return_value = {
            "message": {"role": "assistant", "content": "Hey, it's time to drink water."}
        }
        agent = _fake_agent(stream=False)
        agent.turn.reminder_due_payload = {
            "id": "rid-1",
            "task": "drink water",
            "when": "2026-02-18T12:45:00+00:00",
            "notes": "",
        }

        state = Task()
        next_state = state.handle(agent, Event(EventType.TICK))

        self.assertIsInstance(next_state, Cleanup)
        self.assertEqual(agent.turn.assistant_text, "Hey, it's time to drink water.")
        agent.output.emit_text.assert_called_once_with("Hey, it's time to drink water.")

    @patch("zenbot.agent.states.task.ollama.chat")
    def test_reminder_without_payload_transitions_to_cleanup(self, chat_mock):
        # Verifies Task transitions to Cleanup when no reminder payload is set.
        agent = _fake_agent(stream=False)
        agent.turn.reminder_due_payload = None

        state = Task()
        next_state = state.handle(agent, Event(EventType.TICK))

        self.assertIsInstance(next_state, Cleanup)
        chat_mock.assert_not_called()
        agent.output.emit_text.assert_not_called()
