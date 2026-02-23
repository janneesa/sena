"""Helper functions for Zenbot."""

from pathlib import Path

def get_system_instructions_path() -> str:
    """Get path to system instructions markdown file.
    
    Returns:
        Absolute path to config/system.md in the project root.
    """
    # Navigate from utils/ -> agent/ -> zenbot/ -> project_root/
    utils_dir = Path(__file__).parent
    agent_dir = utils_dir.parent
    zenbot_dir = agent_dir.parent
    project_root = zenbot_dir.parent
    return str(project_root / "config" / "system.md")