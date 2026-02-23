"""Core Agent class for ZenBot state machine orchestration.

The Agent manages conversation flow using a state machine pattern, processes events through
configured states, maintains conversation history with memory limits, and coordinates with
the LLM backend for response generation.

Configuration is provided via a Settings object that encapsulates all agent and LLM settings.
Settings can be loaded from TOML files and environment variables using load_settings().

Example usage:
    from zenbot.agent.config import load_settings
    from zenbot.agent.agent import Agent
    
    settings = load_settings()
    agent = Agent(settings=settings)
    
    # Dispatch a user message
    event = Event(event_type=EventType.USER_MESSAGE, payload="Hello!")
    agent.dispatch(event)
    agent.drain()  # Process through state machine
"""

from __future__ import annotations

from queue import Queue

from zenbot.agent.config import Settings
from zenbot.agent.context import ContextBuilder
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
from zenbot.agent.utils.output import output_manager


logger = get_logger("zenbot")


class Agent:
    """Synchronous state-machine runtime for chat turns and reminder events.

    The Agent coordinates state transitions (Idle/Generate/UseTools/Task/Cleanup),
    processes queued external events, registers built-in tools, and maintains
    bounded conversation history plus per-turn working state.
    """
    def __init__(self, settings: Settings):
        """Initialize the Agent with configuration settings.
        
        Configuration, including debug mode and logging behavior, is entirely controlled
        by the Settings object. The debug flag from settings.agent.debug determines logging
        level (DEBUG if true; INFO otherwise).
        
        Args:
            settings: A Settings object containing LLM and agent configuration.
                     Can be loaded from files and environment variables using load_settings().
        """
        configure_logging(debug=settings.agent.debug)
        self.settings = settings
        self.state = Idle()
        self._next_state = None

        self.output = output_manager

        self.toolbox = Toolbox()
        self._register_builtin_tools()

        # Build system message from markdown instructions
        context_builder = ContextBuilder(get_system_instructions_path())
        system_message = context_builder.build_system_message()

        self.messages = [
            {"role": "system", "content": system_message}
        ]

        self.turn = Turn()
        self.event_queue: Queue[Event] = Queue()

    def _register_builtin_tools(self) -> None:
        """Register built-in tools available to the agent."""
        self.toolbox.register(DateTimeTool())
        logger.debug("Registered tool: datetime")
        
        # Configure and register reminder tools
        reminder_tool = SetReminderTool()
        reminder_tool.settings = self.settings
        self.toolbox.register(reminder_tool)
        logger.debug("Registered tool: set_reminder")
        
        list_tool = ListRemindersTool()
        list_tool.settings = self.settings
        self.toolbox.register(list_tool)
        logger.debug("Registered tool: list_reminders")
        
        delete_tool = DeleteReminderTool()
        delete_tool.settings = self.settings
        self.toolbox.register(delete_tool)
        logger.debug("Registered tool: delete_reminder")

    def dispatch(self, event: Event) -> None:
        """Handle an external event and transition the state machine.
        
        This method processes an event using the current state's handle() method and stores
        the result as the next pending state. The state machine does not actually transition
        until drain() is called.
        
        Args:
            event: The Event to process (typically USER_MESSAGE from the main loop).
        """
        if event.event_type == EventType.USER_MESSAGE:
            logger.debug("Dispatching USER_MESSAGE")
        if event.event_type == EventType.REMINDER_DUE:
            logger.debug("Dispatching REMINDER_DUE")
        self._next_state = self.state.handle(self, event)

    def enqueue_event(self, event: Event) -> None:
        """Add an external event to the unified queue."""
        self.event_queue.put(event)

    def has_queued_events(self) -> bool:
        """Return True when queued events are waiting to be processed."""
        return not self.event_queue.empty()

    def process_next_queued_event(self) -> bool:
        """Process one queued event through dispatch + drain.

        Returns:
            bool: True if one event was processed, False if queue was empty.
        """
        if self.event_queue.empty():
            return False
        event = self.event_queue.get()
        self.dispatch(event)
        self.drain()
        return True

    def process_queued_events(self) -> int:
        """Process all queued events until the queue is empty.

        Returns:
            int: Number of processed events.
        """
        processed = 0
        while self.process_next_queued_event():
            processed += 1
        return processed

    def drain(self) -> None:
        """Execute pending state transitions until reaching Idle or hitting step limit.
        
        This method runs the state machine's internal loop: it transitions to pending states
        and feeds them TICK events to drive async actions (like LLM generation) until:
        - The machine returns to Idle state, OR
        - The maximum internal steps limit is reached (to prevent infinite loops).
        
        The step limit is configured via settings.agent.max_internal_steps.
        Used after dispatch() to run the state machine until quiescent.
        """
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

        # If we reached the step limit exactly while the next transition is Idle,
        # finalize it here to avoid leaving the machine in a non-idle state.
        if self._next_state is not None and isinstance(self._next_state, Idle):
            self.state = self._next_state
            self._next_state = None

        # Hard guard: recover safely if we're still not done after the step budget.
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
        """Commit the current turn (user input + assistant response) to message history.
        
        Appends the user's text and assistant's response to self.messages if both are non-empty.
        After committing, trims the history to the maximum allowed size and resets the turn.
        
        This is called by the Generate state after the LLM produces a response.
        """
        user_text = self.turn.user_text.strip()
        assistant_text = self.turn.assistant_text.strip()

        if not user_text or not assistant_text:
            self.reset_turn()
            return

        logger.debug("Turn committed")
        self.messages.append({"role": "user", "content": user_text})
        self.messages.append({"role": "assistant", "content": assistant_text})
        self._trim_history()
        self.reset_turn()

    def _trim_history(self) -> None:
        """Trim message history to maximum size, keeping system message + most recent turns.
        
        Preserves the system message at index 0 and keeps only the last max_history_messages
        of the remaining history. This prevents unbounded memory growth over long conversations.
        
        The history size limit is configured via settings.agent.max_history_messages.
        Internal method; called automatically after commit_turn().
        """
        if not self.messages:
            return

        system_message = self.messages[0]
        history = self.messages[1:]
        if len(history) <= self.settings.agent.max_history_messages:
            return

        self.messages = [system_message] + history[-self.settings.agent.max_history_messages :]

    def reset_turn(self) -> None:
        """Reset the current turn without committing to history.
        
        Clears user_text, assistant_text, assistant streaming flag,
        pending_tool_calls, tool_results, and
        working LLM messages from the current turn.
        This can be used to discard an in-progress turn if needed.
        """
        self.turn.user_text = ""
        self.turn.assistant_text = ""
        self.turn.reminder_due_payload = None
        self.turn.assistant_streamed = False
        self.turn.pending_tool_calls.clear()
        self.turn.tool_results.clear()
        self.turn.llm_messages.clear()
