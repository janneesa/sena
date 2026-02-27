"""Load system instructions from markdown files."""

from __future__ import annotations

from pathlib import Path

from sena.agent.utils.logging import get_logger


logger = get_logger("sena")


def load_system_message(instructions_path: Path | str) -> str:
    """Load system instructions from markdown files with fallback.
    
    Attempts to load from the override file first, then the default,
    then returns a built-in fallback if neither exists.
    
    Args:
        instructions_path: Path to the override system.md file.
        
    Returns:
        str: The system message content.
    """
    instructions_path = Path(instructions_path)
    default_instructions_path = instructions_path.with_name("default_system.md")

    # Try override first
    override = _read_nonempty(instructions_path)
    if override is not None:
        logger.debug(f"Loaded system instructions from: {instructions_path}")
        return override

    # Fall back to default
    default = _read_nonempty(default_instructions_path)
    if default is not None:
        logger.debug(f"Loaded default system instructions from: {default_instructions_path}")
        return default

    # Final fallback
    logger.debug("No system instructions found; using built-in fallback")
    return "You are a helpful AI assistant."


def _read_nonempty(path: Path) -> str | None:
    """Read file content and return stripped text when non-empty."""
    if not path.exists():
        return None
    content = path.read_text(encoding="utf-8").strip()
    return content or None
