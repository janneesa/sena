"""Helper functions for Zenbot."""

import os
from pathlib import Path

def get_project_root() -> Path:
    """Return absolute project root path."""
    return Path(__file__).resolve().parents[3]


def get_workspace_root() -> Path:
    """Return writable workspace root path.

    Uses WORKSPACE_ROOT when provided, otherwise defaults to project_root/workspace.
    """
    workspace_root = os.getenv("WORKSPACE_ROOT", "").strip()
    if workspace_root:
        return Path(workspace_root)
    return get_project_root() / "workspace"


def get_system_instructions_path() -> str:
    """Return absolute path to config/system.md."""
    return str(get_project_root() / "config" / "system.md")