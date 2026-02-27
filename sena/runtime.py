"""Runtime helpers for process-level configuration and shutdown handling."""

from __future__ import annotations

import logging
import os
import signal
import threading

logger = logging.getLogger("sena")


def configure_ollama_endpoint() -> None:
    """Configure Ollama SDK endpoint from OLLAMA_BASE_URL.

    The ollama Python SDK reads OLLAMA_HOST. Sena standardizes on OLLAMA_BASE_URL
    as the user-facing variable and maps it once at startup.
    """
    base_url = os.getenv("OLLAMA_BASE_URL", "").strip()
    if base_url:
        os.environ["OLLAMA_HOST"] = base_url


def install_signal_handlers(stop_event: threading.Event) -> dict[int, signal.Handlers]:
    """Install SIGINT/SIGTERM handlers that request graceful shutdown.

    Returns previous handlers so callers can restore them after exit.
    """
    previous_handlers: dict[int, signal.Handlers] = {}

    def _on_signal(signum, _frame) -> None:
        signal_name = signal.Signals(signum).name
        logger.info(f"Received {signal_name}; requesting shutdown")
        stop_event.set()

    for signum in (signal.SIGINT, signal.SIGTERM):
        previous_handlers[signum] = signal.getsignal(signum)
        signal.signal(signum, _on_signal)

    return previous_handlers


def restore_signal_handlers(previous_handlers: dict[int, signal.Handlers]) -> None:
    """Restore previously installed signal handlers."""
    for signum, handler in previous_handlers.items():
        signal.signal(signum, handler)
