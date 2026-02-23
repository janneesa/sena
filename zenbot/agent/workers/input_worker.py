"""Input worker for reading user input and enqueueing messages."""

from __future__ import annotations

import threading
from typing import TYPE_CHECKING

from zenbot.agent.types import Event, EventType
from zenbot.agent.utils.logging import get_logger

if TYPE_CHECKING:
    from zenbot.agent.agent import Agent


logger = get_logger("zenbot")


class InputWorker:
    """Background worker that reads user input and enqueues messages to the agent."""

    def __init__(self, agent: Agent, stop_event: threading.Event | None = None):
        """Initialize the input worker with an agent reference.
        
        Args:
            agent: The Agent instance that receives input events.
            stop_event: Optional shared stop event to coordinate shutdown.
        """
        self.agent = agent
        self._stop_event = stop_event or threading.Event()
        self._thread: threading.Thread | None = None

    def start(self) -> None:
        """Start the background input reading thread."""
        if self._thread and self._thread.is_alive():
            return

        self._thread = threading.Thread(target=self._run, daemon=True, name="input-worker")
        self._thread.start()
        logger.debug("Input worker started")

    def stop(self) -> None:
        """Request worker stop and wait briefly for shutdown."""
        self._stop_event.set()
        if self._thread:
            self._thread.join(timeout=0.5)

    def _run(self) -> None:
        """Worker loop that reads user input until stopped."""
        while not self._stop_event.is_set():
            try:
                raw = input("> ")
            except (EOFError, StopIteration):
                self._stop_event.set()
                break
            except Exception:
                logger.exception("Input worker failed while reading user input")
                self._stop_event.set()
                break

            user_input = raw.strip()
            if not user_input:
                continue

            if user_input.lower() in {"exit", "quit"}:
                logger.info("User requested exit")
                self._stop_event.set()
                break

            self.agent.enqueue_event(
                Event(event_type=EventType.USER_MESSAGE, payload=user_input)
            )
