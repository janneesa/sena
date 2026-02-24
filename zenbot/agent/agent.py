"""Core Agent class for ZenBot state machine orchestration.

The Agent manages conversation flow using a state machine pattern, processes events through
configured states, maintains conversation history with memory limits, and coordinates with
the LLM backend for response generation.
"""

from __future__ import annotations

from queue import Queue

from zenbot.agent.config import Settings
from zenbot.agent.context import load_system_message
from zenbot.agent.states.idle import Idle
from zenbot.agent.tools import (
    DateTimeTool,
    SetReminderTool,
    ListRemindersTool,
    DeleteReminderTool,
    Toolbox,
)
from zenbot.agent.types import Event, EventType, Turn
from zenbot.agent.utils.helpers import get_system_instructions_path
from zenbot.agent.utils.logging import configure_logging, get_logger
from zenbot.agent.workers.terminal_communication_manager import terminal_communication_manager


logger = get_logger("zenbot")


class Agent:
    """Coordinates state transitions, tool execution, and turn history."""
    def __init__(self, settings: Settings):
        """Initialize runtime state, tools, and system instructions."""
        configure_logging(debug=settings.agent.debug)
        self.settings = settings
        self.state = Idle()
        self._next_state = None

        self.output = terminal_communication_manager

        self.toolbox = Toolbox()
        self._register_builtin_tools()

        # Load system message from markdown instructions
        system_message = load_system_message(get_system_instructions_path())

        self.messages = [
            {"role": "system", "content": system_message}
        ]

        self.turn = Turn()
        self.event_queue: Queue[Event] = Queue()

    def _register_builtin_tools(self) -> None:
        """Register built-in tools available to the agent."""
        for tool_class in (DateTimeTool, SetReminderTool, ListRemindersTool, DeleteReminderTool):
            tool = tool_class()
            if hasattr(tool, "settings"):
                tool.settings = self.settings
            self.toolbox.register(tool)
            logger.debug(f"Registered tool: {tool.name}")

    def dispatch(self, event: Event) -> None:
        """Handle an external event and set the next pending state."""
        if event.event_type in (EventType.USER_MESSAGE, EventType.REMINDER_DUE):
            logger.debug(f"Dispatching {event.event_type.value.upper()}")
        self._next_state = self.state.handle(self, event)

    def enqueue_event(self, event: Event) -> None:
        """Add an external event to the unified queue."""
        self.event_queue.put(event)

    def has_queued_events(self) -> bool:
        """Return True when queued events are waiting to be processed."""
        return not self.event_queue.empty()

    def process_next_queued_event(self) -> bool:
        """Process a single queued event through dispatch + drain."""
        if not self.has_queued_events():
            return False
        event = self.event_queue.get()
        self.dispatch(event)
        self.drain()
        return True

    def process_queued_events(self) -> int:
        """Drain the external event queue and return processed count."""
        processed = 0
        while self.has_queued_events():
            self.process_next_queued_event()
            processed += 1
        return processed

    def drain(self) -> None:
        """Apply pending transitions until Idle or step budget is reached."""
        steps = 0
        while self._next_state is not None and steps < self.settings.agent.max_internal_steps:
            self.state = self._next_state
            self._next_state = None

            logger.debug(f"Transition: {self.state.name}")

            if isinstance(self.state, Idle):
                break

            tick = Event(event_type=EventType.TICK)
            self._next_state = self.state.handle(self, tick)
            steps += 1

        if self._next_state is not None and isinstance(self._next_state, Idle):
            self.state = self._next_state
            self._next_state = None

        if self._next_state is not None and steps >= self.settings.agent.max_internal_steps:
            logger.warning("Max internal steps reached")
            self.output.emit_text(
                "I hit an internal step limit while processing that request. "
                "Please split it into smaller steps and try again."
            )
            self.reset_turn()
            self.state = Idle()
            self._next_state = None
            return

        if isinstance(self.state, Idle):
            self._next_state = None

    def commit_turn(self) -> None:
        """Commit user/assistant text to history when both are non-empty."""
        user_text = self.turn.user_text.strip()
        assistant_text = self.turn.assistant_text.strip()

        if not user_text or not assistant_text:
            self.reset_turn()
            return

        self.messages.append({"role": "user", "content": user_text})
        self.messages.append({"role": "assistant", "content": assistant_text})
        logger.debug("Turn committed")
        self._trim_history()
        self.reset_turn()

    def _trim_history(self) -> None:
        """Keep system message and the latest configured history window."""
        if not self.messages:
            return

        system_message = self.messages[0]
        history = self.messages[1:]
        if len(history) <= self.settings.agent.max_history_messages:
            return

        self.messages = [system_message] + history[-self.settings.agent.max_history_messages :]

    def reset_turn(self) -> None:
        """Reset ephemeral turn state."""
        self.turn = Turn()
