import unittest
from types import SimpleNamespace
from unittest.mock import patch

from zenbot.agent.agent import Agent
from zenbot.agent.states.idle import Idle
from zenbot.agent.types import Event, EventType


class _ReturnsIdleState:
    name = "RETURNS_IDLE"

    def handle(self, _agent, _event):
        return Idle()


class _LoopState:
    name = "LOOP"

    def handle(self, _agent, _event):
        return self


class TestAgent(unittest.TestCase):
    def _settings(self, max_steps: int = 5, max_history: int = 4):
        return SimpleNamespace(
            llm=SimpleNamespace(model="qwen", stream=False, think=False),
            agent=SimpleNamespace(max_internal_steps=max_steps, max_history_messages=max_history, debug=False),
        )

    @patch("zenbot.agent.agent.get_system_instructions_path", return_value="d:/missing.md")
    def test_commit_turn_appends_and_resets(self, _path_mock):
        # Verifies commit_turn writes user/assistant messages and clears turn state.
        agent = Agent(settings=self._settings())
        agent.turn.user_text = "hello"
        agent.turn.assistant_text = "world"

        before = len(agent.messages)
        agent.commit_turn()

        self.assertEqual(len(agent.messages), before + 2)
        self.assertEqual(agent.messages[-2]["role"], "user")
        self.assertEqual(agent.messages[-1]["role"], "assistant")
        self.assertEqual(agent.turn.user_text, "")
        self.assertEqual(agent.turn.assistant_text, "")

    @patch("zenbot.agent.agent.get_system_instructions_path", return_value="d:/missing.md")
    def test_trim_history_keeps_system_and_recent(self, _path_mock):
        # Verifies history trimming keeps the system prompt and newest messages only.
        agent = Agent(settings=self._settings(max_history=2))
        agent.messages = [{"role": "system", "content": "sys"}] + [
            {"role": "user", "content": "u1"},
            {"role": "assistant", "content": "a1"},
            {"role": "user", "content": "u2"},
            {"role": "assistant", "content": "a2"},
        ]

        agent._trim_history()

        self.assertEqual(len(agent.messages), 3)
        self.assertEqual(agent.messages[0]["role"], "system")
        self.assertEqual(agent.messages[1]["content"], "u2")
        self.assertEqual(agent.messages[2]["content"], "a2")

    @patch("zenbot.agent.agent.get_system_instructions_path", return_value="d:/missing.md")
    def test_dispatch_sets_next_state(self, _path_mock):
        # Verifies dispatch stores a pending next state.
        agent = Agent(settings=self._settings())
        event = Event(event_type=EventType.USER_MESSAGE, payload="hi")
        agent.dispatch(event)
        self.assertIsNotNone(agent._next_state)

    @patch("zenbot.agent.agent.get_system_instructions_path", return_value="d:/missing.md")
    def test_drain_stops_at_idle(self, _path_mock):
        # Verifies drain stops cleanly once Idle state is reached.
        agent = Agent(settings=self._settings(max_steps=3))
        agent._next_state = Idle()
        agent.drain()
        self.assertIsInstance(agent.state, Idle)
        self.assertIsNone(agent._next_state)

    @patch("zenbot.agent.agent.get_system_instructions_path", return_value="d:/missing.md")
    def test_commit_turn_resets_when_user_text_missing(self, _path_mock):
        # Verifies reminder-only turns are reset even when not committed to history.
        agent = Agent(settings=self._settings())
        agent.turn.user_text = ""
        agent.turn.assistant_text = "Hey, it's time now"
        agent.turn.reminder_due_payload = {"id": "r1"}

        before = len(agent.messages)
        agent.commit_turn()

        self.assertEqual(len(agent.messages), before)
        self.assertEqual(agent.turn.user_text, "")
        self.assertEqual(agent.turn.assistant_text, "")
        self.assertIsNone(agent.turn.reminder_due_payload)

    @patch("zenbot.agent.agent.get_system_instructions_path", return_value="d:/missing.md")
    def test_process_next_queued_event_dispatches_and_drains(self, _path_mock):
        # Verifies queued events run through dispatch + drain.
        agent = Agent(settings=self._settings())
        with patch.object(agent, "dispatch") as dispatch_mock, patch.object(agent, "drain") as drain_mock:
            agent.enqueue_event(Event(event_type=EventType.USER_MESSAGE, payload="hello"))
            processed = agent.process_next_queued_event()

        self.assertTrue(processed)
        dispatch_mock.assert_called_once()
        drain_mock.assert_called_once()

    @patch("zenbot.agent.agent.get_system_instructions_path", return_value="d:/missing.md")
    def test_drain_applies_pending_idle_when_limit_reached(self, _path_mock):
        # Verifies drain does not get stuck when step budget is hit with next_state=Idle.
        agent = Agent(settings=self._settings(max_steps=1))
        agent._next_state = _ReturnsIdleState()

        agent.drain()

        self.assertIsInstance(agent.state, Idle)
        self.assertIsNone(agent._next_state)

    @patch("zenbot.agent.agent.get_system_instructions_path", return_value="d:/missing.md")
    def test_drain_recovers_to_idle_after_true_step_limit_overrun(self, _path_mock):
        # Verifies hard-guard recovery when internal loop exceeds allowed steps.
        agent = Agent(settings=self._settings(max_steps=1))
        agent._next_state = _LoopState()
        with patch.object(agent.output, "emit_text") as emit_text_mock:
            agent.drain()

        self.assertIsInstance(agent.state, Idle)
        self.assertIsNone(agent._next_state)
        emit_text_mock.assert_called_once()
