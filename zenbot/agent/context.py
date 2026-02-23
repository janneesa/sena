"""Simple context builder for loading system instructions."""

from __future__ import annotations

from pathlib import Path

from zenbot.agent.utils.logging import get_logger


logger = get_logger("zenbot")


class ContextBuilder:
    """Builds system context from markdown instructions."""

    def __init__(self, instructions_path: Path | str):
        """Initialize with path to the override instructions file.
        
        Args:
            instructions_path: Path to the override markdown file (system.md).
        """
        self.instructions_path = Path(instructions_path)
        self.default_instructions_path = self.instructions_path.with_name(
            "default_system.md"
        )

    def build_system_message(self) -> str:
        """Load and return the system instructions.
        
        Returns:
            str: The system message content.
        """
        override = self._read_nonempty(self.instructions_path)
        if override is not None:
            logger.debug(f"Loaded system instructions override from: {self.instructions_path}")
            return override

        default = self._read_nonempty(self.default_instructions_path)
        if default is not None:
            logger.debug(f"Loaded default system instructions from: {self.default_instructions_path}")
            return default

        logger.debug("No system instructions found; using built-in fallback prompt")
        return "You are a helpful AI assistant."

    @staticmethod
    def _read_nonempty(path: Path) -> str | None:
        """Read file content and return stripped text when non-empty."""
        if not path.exists():
            return None
        content = path.read_text(encoding="utf-8").strip()
        return content or None
