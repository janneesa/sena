from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel

from zenbot.agent.tools.base import Tool


class DateTimeArgs(BaseModel):
    """Arguments for DateTimeTool."""


class DateTimeTool(Tool):
    """Get the current local date and time.
    
    Dev notes:
    - Used when user asks for time/date context (e.g., "What time is it?").
    - Returns structured time fields (iso, date, time, timestamp, timezone).
    - Always available; no initialization needed.
    """

    name = "datetime"
    description = "Tool to get the current date and time when the user asks for time or date context. Examples: 'What time is it?', 'What's today's date?', 'Tell me the current time'"
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
