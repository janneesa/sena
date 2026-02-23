from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel

from zenbot.agent.tools.base import Tool


class DateTimeArgs(BaseModel):
    """Arguments for DateTimeTool."""


class DateTimeTool(Tool):
    """
    Tool to get the current local date and time when the user asks for time or date context.

    Examples:
    - "What time is it?"
    - "What's today's date?"
    - "Tell me the current time"

    Additional notes:
    - Returns structured time fields (`iso`, `date`, `time`, `timestamp`, `timezone`).
    - Use this tool for factual current-time answers instead of guessing.
    """

    name = "datetime"
    user_message = "Checking current date and time..."
    ArgsModel = DateTimeArgs

    def run(self, args: DateTimeArgs) -> dict[str, object]:
        now = datetime.now().astimezone()
        return {
            "iso": now.isoformat(),
            "date": now.date().isoformat(),
            "time": now.time().isoformat(timespec="seconds"),
            "timestamp": now.timestamp(),
            "timezone": str(now.tzinfo),
        }
