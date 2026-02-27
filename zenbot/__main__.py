"""
Entry point for running ZenBot:

    uv run python -m zenbot

Configuration is loaded from:
1. Environment variables (ZENBOT_* prefix)
2. config/local.toml (if it exists)
3. config/default.toml (default settings)

See .env.example for available environment variable overrides.
"""

from __future__ import annotations

import threading
import time

from zenbot.runtime import configure_ollama_endpoint as _configure_ollama_endpoint

# Configure Ollama endpoint before importing modules that import ollama.
_configure_ollama_endpoint()

from zenbot.agent import Agent
from zenbot.agent.config import load_settings
from zenbot.agent.workers import ReminderWorker
from zenbot.agent.workers.terminal_communication_manager import terminal_communication_manager
from zenbot.agent.utils.database import DatabaseHelper, get_database_path
from zenbot.agent.utils.logging import get_logger
from zenbot.runtime import (
    install_signal_handlers as _install_signal_handlers,
    restore_signal_handlers as _restore_signal_handlers,
)


logger = get_logger("zenbot")


def main() -> None:
    """Run ZenBot interactive chat loop.
    
    Loads configuration from files and environment variables, initializes the Agent,
    and enters an interactive loop to accept user input and generate responses.
    """
    stop_event = threading.Event()
    previous_signal_handlers = _install_signal_handlers(stop_event)
    reminder_worker = None
    workers_started = False

    try:
        try:
            settings = load_settings()
        except (RuntimeError, ValueError) as e:
            logger.error(f"Configuration error: {e}")
            terminal_communication_manager.emit_text(f"Configuration error: {e}")
            return

        agent = Agent(settings=settings)
        db = DatabaseHelper(get_database_path())

        # Configure and start background workers
        reminder_worker = ReminderWorker(
            agent=agent,
            db=db,
            poll_seconds=settings.agent.reminder_poll_seconds,
        )
        reminder_worker.start()
        terminal_communication_manager.start(agent=agent, stop_event=stop_event)
        workers_started = True
        logger.info("ZenBot started and workers initialized")

        terminal_communication_manager.emit_text("ZenBot (type 'exit' to quit)")
        terminal_communication_manager.emit_text("")

        # Main loop: process events until stop requested
        while not stop_event.is_set():
            if agent.has_queued_events():
                agent.process_queued_events()
            else:
                time.sleep(0.05)

        if agent.has_queued_events():
            agent.process_queued_events()
    finally:
        stop_event.set()
        if workers_started:
            terminal_communication_manager.stop()
        if reminder_worker is not None:
            reminder_worker.stop()
        _restore_signal_handlers(previous_signal_handlers)
        if workers_started:
            logger.info("ZenBot shutdown complete")


if __name__ == "__main__":
    main()
