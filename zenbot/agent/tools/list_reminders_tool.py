"""List reminders tool for ZenBot."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel

from zenbot.agent.tools.base import Tool
from zenbot.agent.utils.database import DatabaseHelper, get_database_path
from zenbot.agent.utils.datetime_utils import format_reminder_when
from zenbot.agent.utils.logging import get_logger


logger = get_logger("zenbot")


class ListRemindersArgs(BaseModel):
    """Arguments for ListRemindersTool (no arguments needed)."""
    pass


class ListRemindersTool(Tool):
    """
    Tool to list active reminders when the user asks what reminders they currently have.

    Examples:
    - "Show me my reminders"
    - "What reminders do I have?"
    - "Can you list my reminders?"

    Additional notes:
    - This tool is the source of truth for active reminder state.
    - Do not answer reminder-list requests from memory.
    - Returns both structured reminder data and a deterministic human-readable summary.
    """

    name = "list_reminders"
    user_message = "Fetching your reminders..."
    ArgsModel = ListRemindersArgs

    def __init__(self):
        """Initialize the list reminders tool."""
        self.db = DatabaseHelper(get_database_path())

    def run(self, args: ListRemindersArgs) -> dict[str, object]:
        """List all active reminders.
        
        Args:
            args: ListRemindersArgs (no arguments needed).
        
        Returns:
            dict with reminders list or empty message.
        """
        # Get all active reminders (exclude completed)
        reminders = self.db.get_all_reminders(include_completed=False)
        
        if not reminders:
            logger.debug("tool=list_reminders event=empty_result")
            return {
                "success": True,
                "count": 0,
                "message": "You don't have any active reminders.",
                "reminders": []
            }
        
        # Format reminders as numbered list
        formatted_reminders = []
        for i, reminder in enumerate(reminders, 1):
            when_human = self._format_when_for_display(str(reminder["when"]))
            formatted_reminders.append({
                "number": i,
                "task": reminder["task"],
                "when": reminder["when"],
                "when_human": when_human,
                "id": reminder["id"],
                "created_at": reminder.get("created_at", ""),
                "notes": reminder.get("notes")
            })
        
        summary = self._build_summary(formatted_reminders)
        logger.debug(f"tool=list_reminders event=success count={len(reminders)}")
        
        return {
            "success": True,
            "count": len(reminders),
            "reminders": formatted_reminders,
            "summary": summary,
        }

    def _build_summary(self, reminders: list[dict]) -> str:
        """Generate a deterministic summary message from reminder data."""
        reminder_lines = "\n".join(
            f"{i}. **{r['task']}** – {r.get('when_human', r['when'])}"
            for i, r in enumerate(reminders, 1)
        )
        return f"You have {len(reminders)} reminder(s):\n\n{reminder_lines}"

    def _format_when_for_display(self, when_value: str, now: datetime | None = None) -> str:
        """Format reminder timestamp for user-friendly list output."""
        return format_reminder_when(when_value, now=now)
