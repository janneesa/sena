"""Helper functions for Zenbot."""

from pathlib import Path

def get_project_root() -> Path:
    """Return absolute project root path."""
    return Path(__file__).resolve().parents[3]


def get_system_instructions_path() -> str:
    """Return absolute path to config/system.md."""
    return str(get_project_root() / "config" / "system.md")