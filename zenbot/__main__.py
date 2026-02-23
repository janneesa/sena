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

from zenbot.agent import Agent
from zenbot.agent.config import load_settings
from zenbot.agent.workers import InputWorker, ReminderWorker
from zenbot.agent.utils.database import DatabaseHelper, get_database_path
from zenbot.agent.utils.logging import get_logger
from zenbot.agent.utils.output import output_manager


logger = get_logger("zenbot")


def main() -> None:
    """Run ZenBot interactive chat loop.
    
    Loads configuration from files and environment variables, initializes the Agent,
    and enters an interactive loop to accept user input and generate responses.
    """
    try:
        settings = load_settings()
    except (RuntimeError, ValueError) as e:
        logger.error(f"Configuration error: {e}")
        output_manager.emit_text(f"Configuration error: {e}")
        return
    
    agent = Agent(settings=settings)
    db = DatabaseHelper(get_database_path())
    
    # Configure and start background workers
    reminder_worker = ReminderWorker(
        agent=agent,
        db=db,
        poll_seconds=settings.agent.reminder_poll_seconds,
    )
    stop_event = threading.Event()
    input_worker = InputWorker(agent=agent, stop_event=stop_event)

    reminder_worker.start()
    input_worker.start()
    logger.info("ZenBot started and workers initialized")

    output_manager.emit_text("ZenBot (type 'exit' to quit)")
    output_manager.emit_text("")

    # Main loop: process events until stop requested
    try:
        while not stop_event.is_set():
            if agent.has_queued_events():
                agent.process_queued_events()
            else:
                time.sleep(0.05)

        if agent.has_queued_events():
            agent.process_queued_events()
    finally:
        stop_event.set()
        input_worker.stop()
        reminder_worker.stop()
        logger.info("ZenBot shutdown complete")


if __name__ == "__main__":
    main()
