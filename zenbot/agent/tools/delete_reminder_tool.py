"""Delete reminder tool for ZenBot."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field

from zenbot.agent.tools.base import Tool
from zenbot.agent.utils.json_utils import call_llm_with_format
from zenbot.agent.utils.database import DatabaseHelper, get_database_path
from zenbot.agent.utils.datetime_utils import is_datetime_past
from zenbot.agent.utils.logging import get_logger


logger = get_logger("zenbot")


class DeleteReminderArgs(BaseModel):
    """Arguments for DeleteReminderTool."""

    request: str = Field(
        ...,
        min_length=1,
        description=(
            "The user's deletion request describing which reminder to delete. "
            "Examples: 'delete the water reminder', "
            "'remove the reminder about emails', "
            "'cancel my 5pm reminder'. "
            "Can reference the task, time, or position in the list."
        ),
    )


class ReminderMatch(BaseModel):
    """Structured match result from LLM identifying which reminder to delete."""

    reminder_id: str = Field(
        ...,
        min_length=1,
        description="The exact ID of the reminder that matches the user's deletion request.",
    )
    confidence: str = Field(
        default="high",
        description="Confidence level of the match: 'high', 'medium', or 'low'.",
    )
    reason: str | None = Field(
        default=None,
        description="Brief explanation of why this reminder was matched.",
    )


class DeleteConfirmation(BaseModel):
    """Structured confirmation message after deletion."""

    confirmation_message: str = Field(
        ...,
        min_length=1,
        description="A short, friendly message confirming which reminder was deleted.",
    )


class DeleteReminderTool(Tool):
    """
    Tool to delete an existing reminder when the user asks to remove or cancel one.

    Examples:
    - "Delete my water reminder"
    - "Remove the reminder about emails"
    - "Cancel reminder number 2"

    Additional notes:
    - Pass the user's deletion request in `request`; matching is handled by the tool.
    - The tool verifies the match, deletes the reminder, and returns a confirmation.
    - Includes best-effort cleanup of past reminders after successful deletion.
    """

    name = "delete_reminder"
    user_message = "Deleting your reminder..."
    ArgsModel = DeleteReminderArgs

    def __init__(self):
        """Initialize the delete reminder tool."""
        self.settings = None  # Injected by Agent during registration
        self.db = DatabaseHelper(get_database_path())

    def run(self, args: DeleteReminderArgs) -> dict[str, object]:
        """Execute the delete reminder workflow: match, delete, confirm, cleanup old reminders.
        
        Args:
            args: DeleteReminderArgs containing the user's deletion request.
        
        Returns:
            dict with either success confirmation or error details.
        """
        # Step 1: Get all active reminders
        reminders = self.db.get_all_reminders(include_completed=False)
        
        if not reminders:
            logger.debug("tool=delete_reminder event=no_active_reminders")
            return {
                "error": "You don't have any active reminders to delete."
            }
        
        # Step 2: Use LLM to match user's request to a specific reminder
        match = self._match_reminder(args.request, reminders)
        if match is None:
            logger.warning("tool=delete_reminder event=match_failed")
            return {
                "error": "Could not identify which reminder you want to delete. Please be more specific."
            }
        
        # Step 3: Verify the reminder exists and get its details
        reminder = self.db.get_reminder(match.reminder_id)
        if reminder is None:
            logger.warning(f"tool=delete_reminder event=matched_missing_id reminder_id={match.reminder_id}")
            return {
                "error": "The matched reminder could not be found in the database."
            }
        
        # Step 4: Delete the reminder
        try:
            deleted = self.db.delete_reminder(match.reminder_id)
            if not deleted:
                logger.warning(f"tool=delete_reminder event=db_delete_returned_false reminder_id={match.reminder_id}")
                return {
                    "error": "Failed to delete the reminder from the database."
                }
        except Exception as exc:
            logger.exception("tool=delete_reminder event=db_delete_failed")
            return {
                "error": f"Could not delete reminder due to error: {exc}"
            }
        
        # Step 5: Auto-cleanup any past reminders
        self._cleanup_past_reminders()
        
        # Step 6: Generate confirmation message
        confirmation = self._build_confirmation(reminder)
        
        return {
            "success": True,
            "confirmation": confirmation,
            "deleted_reminder": {
                "task": reminder["task"],
                "when": reminder["when"],
                "id": reminder["id"]
            }
        }

    def _match_reminder(self, user_request: str, reminders: list[dict[str, Any]]) -> ReminderMatch | None:
        """Use LLM to match user's deletion request to a specific reminder."""
        # Build context with all available reminders
        reminders_context = "Available reminders:\\n"
        for i, reminder in enumerate(reminders, 1):
            reminders_context += f"{i}. ID: {reminder['id']}, Task: {reminder['task']}, When: {reminder['when']}"
            if reminder.get('notes'):
                reminders_context += f", Notes: {reminder['notes']}"
            reminders_context += "\\n"
        
        matching_prompt = (
            "You match a user's deletion request to a specific reminder. "
            "Analyze the user's request and the list of available reminders, "
            "then return the exact ID of the reminder they want to delete. "
            "Return ONLY JSON matching the schema with reminder_id, confidence, and optional reason."
        )
        
        return call_llm_with_format(
            self.settings.llm.model,
            [
                {"role": "system", "content": matching_prompt},
                {"role": "user", "content": f"{reminders_context}\\nUser request: {user_request}"},
            ],
            ReminderMatch,
            self.settings.llm.think,
        )

    def _build_confirmation(self, reminder: dict[str, Any]) -> str:
        """Generate user-facing confirmation after deletion."""
        confirmation_prompt = (
            "Generate a short confirmation message for a deleted reminder. "
            "Return ONLY JSON matching the schema with confirmation_message."
        )
        
        details = f"Deleted reminder - Task: {reminder['task']}, When: {reminder['when']}"
        
        result = call_llm_with_format(
            self.settings.llm.model,
            [
                {"role": "system", "content": confirmation_prompt},
                {"role": "user", "content": details},
            ],
            DeleteConfirmation,
            self.settings.llm.think,
        )
        
        if result is None:
            logger.debug("tool=delete_reminder event=confirmation_fallback")
            return f"Reminder deleted: {reminder['task']} ({reminder['when']})."
        return result.confirmation_message

    def _cleanup_past_reminders(self) -> None:
        """Delete all reminders that are in the past (for automatic housekeeping).
        
        Silently handles errors to avoid disrupting the main deletion operation.
        """
        try:
            reminders = self.db.get_all_reminders(include_completed=False)
            deleted_count = 0
            for reminder in reminders:
                when_str = str(reminder.get("when", "")).strip()
                if when_str and is_datetime_past(when_str):
                    reminder_id = str(reminder.get("id", "")).strip()
                    if reminder_id:
                        if self.db.delete_reminder(reminder_id):
                            deleted_count += 1
            if deleted_count:
                logger.info(f"tool=delete_reminder event=cleanup_deleted count={deleted_count}")
        except Exception:
            # Silently ignore cleanup errors - they're not critical to the deletion
            logger.exception("tool=delete_reminder event=cleanup_failed")

