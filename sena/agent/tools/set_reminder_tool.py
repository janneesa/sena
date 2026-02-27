from __future__ import annotations

from datetime import date, datetime
from typing import Any

from pydantic import BaseModel, Field

from sena.agent.tools.base import Tool
from sena.agent.utils.json_utils import call_llm_with_format
from sena.agent.utils.database import DatabaseHelper, get_database_path
from sena.agent.utils.logging import get_logger
from sena.agent.utils.datetime_utils import (
    parse_time_string,
    resolve_date_expression,
    combine_date_and_time,
)


logger = get_logger("sena")


class SetReminderArgs(BaseModel):
    """Arguments for SetReminderTool."""

    request: str = Field(
        ...,
        min_length=1,
        description=(
            "The user's reminder request preserved exactly as stated. "
            "Examples: 'remind me to drink water in 5 minutes', "
            "'remind me to check emails today at 18:30', "
            "'remind me to call mom tomorrow morning'. "
            "Include both the task (what to remind) and timing (when to remind)."
        ),
    )


class ReminderRequest(BaseModel):
    """LLM extraction model used before deterministic date/time calculations."""

    task: str = Field(
        ...,
        min_length=1,
        description="The reminder task in plain language, such as 'take out the trash'.",
    )
    time: str = Field(
        ...,
        min_length=1,
        description=(
            "The reminder time as written by the user, e.g., '9:15', '9:15 AM', '3:45 PM', '14:30'. "
            "Do not convert or normalize; extract exactly as the user specified."
        ),
    )
    intended_date: str = Field(
        ...,
        min_length=1,
        description=(
            "The intended date expression as extracted from user input, e.g., 'today', 'tomorrow', "
            "'monday', 'tuesday', 'wednesday', 'thursday', 'friday', 'saturday', 'sunday'. "
            "Default to 'today' if the user does not specify. "
            "Do not calculate or interpret the date; extract the user's intent only."
        ),
    )
    notes: str | None = Field(
        default=None,
        description="Optional extra note text relevant to the reminder.",
    )


class ReminderConfirmation(BaseModel):
    """LLM output model for final confirmation text."""

    confirmation_message: str = Field(
        ...,
        min_length=1,
        description="A short, friendly confirmation message for the reminder that was set.",
    )


class SetReminderTool(Tool):
    """Create reminders from natural-language requests.

    Dev notes:
    - Workflow: SetReminderArgs -> ReminderRequest (LLM extract) -> deterministic parsing -> DB save.
    - Uses LLM to extract task, time, date, and notes from user input.
    - Applies deterministic date/time calculation and timezone handling.
    - Returns confirmation message with absolute reminder time.
    """

    name = "set_reminder"
    description = "Tool to set or create a reminder for a task when user asks for a reminder to be created. Examples: 'Remind me to drink water at 14:45', 'Remind me to do my homework tomorrow at 19:15'"
    user_message = "Setting your reminder..."
    ArgsModel = SetReminderArgs

    def __init__(self):
        """Initialize the reminder tool."""
        self.settings = None  # Injected by Agent during registration
        self.db = DatabaseHelper(get_database_path())

    def run(self, args: SetReminderArgs) -> dict[str, object]:
        """Extract, parse, store, and confirm a reminder."""
        reminder_spec = self._extract_reminder_request(args.request)
        if reminder_spec is None:
            logger.warning("tool=set_reminder event=extraction_failed")
            return {
                "error": "Could not extract reminder details. Please specify: what to remind you about, what time, and when (today, tomorrow, or a weekday)."
            }

        hour, minute = self._parse_time(reminder_spec.time)
        if hour is None or minute is None:
            logger.warning(f"tool=set_reminder event=time_parse_failed input={reminder_spec.time}")
            return {
                "error": f"Could not parse time '{reminder_spec.time}'. Please use a format like '9:15', '9:15 AM', or '14:30'."
            }

        target_date = self._resolve_intended_date(reminder_spec.intended_date)
        if target_date is None:
            logger.warning(f"tool=set_reminder event=date_resolve_failed input={reminder_spec.intended_date}")
            return {
                "error": f"Could not interpret date '{reminder_spec.intended_date}'. Use 'today', 'tomorrow', or a weekday name."
            }

        due_iso = self._combine_date_and_time(target_date, hour, minute)

        try:
            record = self.db.add_reminder(
                task=reminder_spec.task,
                when=due_iso,
                notes=reminder_spec.notes,
            )
        except Exception as exc:
            logger.exception("tool=set_reminder event=db_save_failed")
            return {
                "error": f"Could not save reminder due to storage error: {exc}"
            }

        confirmation = self._build_confirmation(
            task=reminder_spec.task,
            target_date=target_date,
            hour=hour,
            minute=minute
        )

        return {
            "success": True,
            "confirmation": confirmation,
            "reminder_id": record["id"],
            "task": reminder_spec.task,
            "when": due_iso,
        }

    def _extract_reminder_request(self, user_request: str) -> ReminderRequest | None:
        """Extract reminder data using LLM with structured format (no date calculations)."""
        extraction_prompt = (
            "You extract reminder request data. Return ONLY JSON that matches the provided schema. "
            "Do not include markdown, explanations, or extra keys. "
            "Extract the task, time, and intended_date exactly as the user specified. "
            "Do NOT perform any date calculations or conversions. "
            "Do NOT convert time to 24-hour format. "
            "CRITICAL: If the user does NOT explicitly mention a date/day (like 'tomorrow', 'friday', 'next monday', 'this weekend'), "
            "you MUST set intended_date to 'today'. Do NOT assume 'tomorrow'. Do NOT guess. Default to 'today' if unsure. "
            "If the user does not specify a time, return an error by returning None."
        )

        return call_llm_with_format(
            self.settings.llm.model,
            [
                {"role": "system", "content": extraction_prompt},
                {"role": "user", "content": user_request},
            ],
            ReminderRequest,
            self.settings.llm.think,
        )

    def _parse_time(self, time_str: str) -> tuple[int | None, int | None]:
        """Parse time string to (hour, minute) tuple.
        
        Delegates to utility function for testability and reuse.
        
        Returns:
            (hour, minute) tuple with hour in 24-hour format, or (None, None) if parsing fails.
        """
        return parse_time_string(time_str)

    def _resolve_intended_date(self, intended_date: str) -> date | None:
        """Resolve date expression to an actual date.
        
        Delegates to utility function for testability and reuse.
        
        Returns:
            datetime.date object, or None if the expression is invalid.
        """
        return resolve_date_expression(intended_date)

    def _combine_date_and_time(self, target_date: date, hour: int, minute: int) -> str:
        """Combine date and time into ISO-8601 timestamp with local timezone.
        
        Delegates to utility function for testability and reuse.
        
        Args:
            target_date: The date to use.
            hour: Hour in 24-hour format (0-23).
            minute: Minute (0-59).
        
        Returns:
            ISO-8601 datetime string with local timezone.
        """
        return combine_date_and_time(target_date, hour, minute)

    def _build_confirmation(
        self, task: str, target_date: date, hour: int, minute: int
    ) -> str:
        """Generate user-facing confirmation message with formatted date and time.
        
        Args:
            task: The reminder task.
            target_date: The date the reminder is set for.
            hour: Hour in 24-hour format.
            minute: Minute.
        
        Returns:
            A friendly confirmation message.
        """
        # Format date as DD.MM.YYYY
        formatted_date = target_date.strftime("%d.%m.%Y")

        # Format time as HH:MM
        formatted_time = f"{hour:02d}:{minute:02d}"

        now_local = datetime.now().astimezone()
        current_time_context = now_local.strftime("%Y-%m-%d %H:%M:%S %Z")

        confirmation_prompt = (
            "You write one short, friendly confirmation for a reminder that was just set. "
            "Use the provided task, date, and time exactly as given. "
            "Do not change or infer a different date or time. "
            "If you mention relative timing (today/tomorrow), it must match the provided current date/time. "
            "Return ONLY JSON that matches the schema with confirmation_message."
        )
        details = (
            f"Current local date/time: {current_time_context}\n"
            f"Task: {task}\n"
            f"Date: {formatted_date}\n"
            f"Time: {formatted_time}"
        )

        result = call_llm_with_format(
            self.settings.llm.model,
            [
                {"role": "system", "content": confirmation_prompt},
                {"role": "user", "content": details},
            ],
            ReminderConfirmation,
            self.settings.llm.think,
        )

        if result is None:
            logger.debug("tool=set_reminder event=confirmation_fallback")
            return f"Reminder set: {task} on {formatted_date} at {formatted_time}."

        return result.confirmation_message
