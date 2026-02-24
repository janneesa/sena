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
    """List active reminders from the database.
    
    Dev notes:
    - Returns all non-completed reminders with human-friendly formatting.
    - Each reminder includes index, task, and formatted time.
    - Returns empty message if no active reminders exist.
    """

    name = "list_reminders"
    description = "Tool to list all active reminders when the user asks to check, show, or view their reminders. Examples: 'Show me my reminders', 'What reminders do I have?', 'List my reminders'"
    user_message = "Fetching your reminders..."
    ArgsModel = ListRemindersArgs

    def __init__(self):
        """Initialize the list reminders tool."""
        self.db = DatabaseHelper(get_database_path())

    def run(self, args: ListRemindersArgs) -> dict[str, object]:
        """Return active reminders with human-friendly labels."""
        reminders = self.db.get_all_reminders(include_completed=False)
        
        if not reminders:
            logger.debug("tool=list_reminders event=empty_result")
            return {
                "success": True,
                "count": 0,
                "message": "You don't have any active reminders.",
                "reminders": []
            }
        
        formatted_reminders = []
        for index, reminder in enumerate(reminders, 1):
            when_human = self._format_when_for_display(str(reminder["when"]))
            formatted_reminders.append({
                "number": index,
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
