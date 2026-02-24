"""Terminal communication manager for interactive CLI I/O.

This component owns terminal-facing communication:
- Reads user input in a background thread
- Enqueues USER_MESSAGE events to the agent
- Emits assistant/status output to terminal safely while input is active
"""

from __future__ import annotations

from abc import ABC, abstractmethod
import threading
from typing import TYPE_CHECKING

from zenbot.agent.types import Event, EventType
from zenbot.agent.utils.logging import get_logger

if TYPE_CHECKING:
    from zenbot.agent.agent import Agent


logger = get_logger("zenbot")

BUSY_MESSAGE = "I'm focusing on another task right now. I will get back to you ASAP!"


class CommunicationManager(ABC):
    """Abstract communication surface for channels that support I/O."""

    @abstractmethod
    def emit_text(self, text: str) -> None:
        """Emit a complete line of text to the user."""
        raise NotImplementedError

    @abstractmethod
    def emit_status(self, text: str) -> None:
        """Emit a non-final status/progress message to the user."""
        raise NotImplementedError

    @abstractmethod
    def begin_stream(self) -> None:
        """Start a streaming assistant output section."""
        raise NotImplementedError

    @abstractmethod
    def emit_stream_chunk(self, chunk: str) -> None:
        """Emit a single chunk of streaming output."""
        raise NotImplementedError

    @abstractmethod
    def end_stream(self) -> None:
        """Close a streaming assistant output section."""
        raise NotImplementedError

    @abstractmethod
    def start(self, agent: Agent, stop_event: threading.Event) -> None:
        """Start inbound input processing for this communication channel."""
        raise NotImplementedError

    @abstractmethod
    def stop(self) -> None:
        """Stop inbound input processing and release resources."""
        raise NotImplementedError


class TerminalCommunicationManager(CommunicationManager):
    """Terminal communication implementation used by the CLI runtime."""

    def __init__(self) -> None:
        self._console_lock = threading.Lock()
        self._stream_open = False
        self._input_active = False
        self._input_prompt = "> "

        self._thread: threading.Thread | None = None
        self._stop_event: threading.Event | None = None
        self._agent: Agent | None = None

    def start(self, agent: Agent, stop_event: threading.Event) -> None:
        if self._thread and self._thread.is_alive():
            return

        self._agent = agent
        self._stop_event = stop_event
        self._thread = threading.Thread(
            target=self._run_input_loop,
            daemon=True,
            name="terminal-communication",
        )
        self._thread.start()
        logger.debug("Terminal communication manager started")

    def stop(self) -> None:
        if self._stop_event is not None:
            self._stop_event.set()
        if self._thread:
            self._thread.join(timeout=0.5)

    def emit_text(self, text: str) -> None:
        if not text:
            return
        self._emit_line(text)

    def emit_status(self, text: str) -> None:
        if not text:
            return
        self._emit_line(text)

    def begin_stream(self) -> None:
        with self._console_lock:
            if self._input_active:
                print()
            self._stream_open = True

    def emit_stream_chunk(self, chunk: str) -> None:
        if not chunk:
            return
        with self._console_lock:
            print(chunk, end="", flush=True)

    def end_stream(self) -> None:
        with self._console_lock:
            if self._stream_open:
                print()
                self._stream_open = False
                self._render_prompt_if_active()

    def _run_input_loop(self) -> None:
        while self._stop_event is not None and not self._stop_event.is_set():
            try:
                raw = self._read_input("> ")
            except (EOFError, StopIteration):
                if self._stop_event is not None:
                    self._stop_event.set()
                break
            except Exception:
                logger.exception("Terminal communication failed while reading user input")
                if self._stop_event is not None:
                    self._stop_event.set()
                break

            user_input = raw.strip()
            if not user_input:
                continue

            if user_input.lower() in {"exit", "quit"}:
                logger.info("User requested exit")
                if self._stop_event is not None:
                    self._stop_event.set()
                break

            if self._agent is not None:
                self._handle_user_message(user_input)

    def _handle_user_message(self, user_input: str) -> None:
        if self._agent is None:
            return

        if self._is_agent_busy():
            self.emit_text(BUSY_MESSAGE)

        self._agent.enqueue_event(
            Event(event_type=EventType.USER_MESSAGE, payload=user_input)
        )

    def _is_agent_busy(self) -> bool:
        if self._agent is None:
            return False

        state_name = getattr(getattr(self._agent, "state", None), "name", "")
        queued_events = bool(self._agent.has_queued_events())
        return state_name != "IDLE" or queued_events

    def _read_input(self, prompt: str) -> str:
        with self._console_lock:
            self._input_active = True
            self._input_prompt = prompt

        try:
            return input(prompt)
        finally:
            with self._console_lock:
                self._input_active = False

    def _emit_line(self, text: str) -> None:
        with self._console_lock:
            if self._input_active:
                print()
            print(text)
            self._render_prompt_if_active()

    def _render_prompt_if_active(self) -> None:
        if self._input_active:
            print(self._input_prompt, end="", flush=True)


terminal_communication_manager = TerminalCommunicationManager()
