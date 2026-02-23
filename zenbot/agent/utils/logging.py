"""Logging utilities for ZenBot using Python's built-in logging module.

Provides simple functions to configure Python's logging system and retrieve loggers.
Uses standard library only; no custom logger classes.
"""

from __future__ import annotations

import logging


def configure_logging(debug: bool = False) -> None:
    """Configure Python's logging system with a standard format.
    
    Calls logging.basicConfig() once with appropriate log level and format.
    Repeated calls have no effect (basicConfig only configures if not already done).
    
    Log level is set to DEBUG if debug=True, otherwise INFO.
    Format includes timestamp, level, logger name, and message.
    
    Args:
        debug: If True, set log level to DEBUG; otherwise use INFO. Defaults to False.
    """
    level = logging.DEBUG if debug else logging.INFO
    logging.basicConfig(
        level=level,
        format="%(asctime)s - %(levelname)s - %(name)s - %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    # Reduce noisy third-party HTTP transport logs in normal runtime output.
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("httpcore").setLevel(logging.WARNING)


def get_logger(name: str) -> logging.Logger:
    """Get a logger instance by name using Python's standard logging.
    
    Simply returns logging.getLogger(name), providing a convenient wrapper
    that encapsulates the logging import site.
    
    Args:
        name: The name of the logger (typically __name__ or 'module.submodule').
    
    Returns:
        logging.Logger: The logger instance for the given name.
    """
    return logging.getLogger(name)
