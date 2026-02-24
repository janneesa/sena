"""Database utilities for ZenBot using SQLite3.

Provides a simple database helper for managing reminders and other persistent data.
Uses Python's built-in sqlite3 library.
"""

from __future__ import annotations

import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from uuid import uuid4

from zenbot.agent.utils.helpers import get_project_root


class DatabaseHelper:
    """Helper class for SQLite database operations."""

    def __init__(self, db_path: Path | str):
        """Initialize database helper with path to SQLite database file.
        
        Args:
            db_path: Path to the SQLite database file.
        """
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_schema()

    def _init_schema(self) -> None:
        """Initialize database schema if tables don't exist."""
        conn = sqlite3.connect(self.db_path)
        try:
            cursor = conn.cursor()
            
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS reminders (
                    id TEXT PRIMARY KEY,
                    created_at TEXT NOT NULL,
                    task TEXT NOT NULL,
                    when_time TEXT NOT NULL,
                    notes TEXT,
                    completed INTEGER DEFAULT 0
                )
            """)
            
            conn.commit()
        finally:
            conn.close()

    def _build_reminder_dict(self, row: sqlite3.Row) -> dict[str, Any]:
        """Convert a database row to a reminder dictionary.
        
        Args:
            row: A sqlite3.Row object from the reminders table.
        
        Returns:
            dict: Reminder record with id, created_at, task, when, and optional notes/completed fields.
        """
        reminder = {
            "id": row["id"],
            "created_at": row["created_at"],
            "task": row["task"],
            "when": row["when_time"],
        }
        if row["notes"]:
            reminder["notes"] = row["notes"]
        if row["completed"]:
            reminder["completed"] = bool(row["completed"])
        return reminder

    @staticmethod
    def _validate_required_text(value: Any, field_name: str) -> str:
        """Validate required text fields before DB writes.

        Args:
            value: The value to validate.
            field_name: Field name for error messages.

        Returns:
            str: Trimmed text value.

        Raises:
            ValueError: If value is missing or not a non-empty string.
        """
        if not isinstance(value, str):
            raise ValueError(f"{field_name} must be a string")
        cleaned = value.strip()
        if not cleaned:
            raise ValueError(f"{field_name} must be a non-empty string")
        return cleaned

    @staticmethod
    def _validate_optional_text(value: Any, field_name: str) -> str | None:
        """Validate optional text fields before DB writes.

        Args:
            value: The value to validate.
            field_name: Field name for error messages.

        Returns:
            str | None: Trimmed text value or None.

        Raises:
            ValueError: If value is not a string when provided.
        """
        if value is None:
            return None
        if not isinstance(value, str):
            raise ValueError(f"{field_name} must be a string")
        cleaned = value.strip()
        return cleaned or None

    def add_reminder(
        self,
        task: str,
        when: str,
        notes: str | None = None
    ) -> dict[str, Any]:
        """Add a new reminder to the database.
        
        Args:
            task: The reminder task description.
            when: The reminder time expression.
            notes: Optional notes for the reminder.
        
        Returns:
            dict: The created reminder record with id, created_at, task, when, notes.
        """
        task = self._validate_required_text(task, "task")
        when = self._validate_required_text(when, "when")
        notes = self._validate_optional_text(notes, "notes")
        reminder_id = str(uuid4())
        created_at = datetime.now(timezone.utc).isoformat()
        
        conn = sqlite3.connect(self.db_path)
        try:
            cursor = conn.cursor()
            cursor.execute(
                """
                INSERT INTO reminders (id, created_at, task, when_time, notes)
                VALUES (?, ?, ?, ?, ?)
                """,
                (reminder_id, created_at, task, when, notes)
            )
            conn.commit()
        finally:
            conn.close()
        
        record = {
            "id": reminder_id,
            "created_at": created_at,
            "task": task,
            "when": when,
        }
        if notes:
            record["notes"] = notes
        
        return record

    def get_all_reminders(self, include_completed: bool = False) -> list[dict[str, Any]]:
        """Get all reminders from the database.
        
        Args:
            include_completed: Whether to include completed reminders.
        
        Returns:
            list: List of reminder records as dictionaries.
        """
        conn = sqlite3.connect(self.db_path)
        try:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            
            if include_completed:
                cursor.execute("SELECT * FROM reminders ORDER BY created_at DESC")
            else:
                cursor.execute(
                    "SELECT * FROM reminders WHERE completed = 0 ORDER BY created_at DESC"
                )
            
            rows = cursor.fetchall()
        finally:
            conn.close()
        
        return [self._build_reminder_dict(row) for row in rows]

    def get_reminder(self, reminder_id: str) -> dict[str, Any] | None:
        """Get a specific reminder by ID.
        
        Args:
            reminder_id: The reminder ID.
        
        Returns:
            dict or None: The reminder record if found, None otherwise.
        """
        reminder_id = self._validate_required_text(reminder_id, "reminder_id")
        conn = sqlite3.connect(self.db_path)
        try:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM reminders WHERE id = ?", (reminder_id,))
            row = cursor.fetchone()
        finally:
            conn.close()
        
        if not row:
            return None
        
        return self._build_reminder_dict(row)

    def mark_completed(self, reminder_id: str) -> bool:
        """Mark a reminder as completed.
        
        Args:
            reminder_id: The reminder ID.
        
        Returns:
            bool: True if reminder was found and marked completed, False otherwise.
        """
        reminder_id = self._validate_required_text(reminder_id, "reminder_id")
        conn = sqlite3.connect(self.db_path)
        try:
            cursor = conn.cursor()
            cursor.execute(
                "UPDATE reminders SET completed = 1 WHERE id = ?",
                (reminder_id,)
            )
            conn.commit()
            return cursor.rowcount > 0
        finally:
            conn.close()

    def delete_reminder(self, reminder_id: str) -> bool:
        """Delete a reminder from the database.
        
        Args:
            reminder_id: The reminder ID.
        
        Returns:
            bool: True if reminder was found and deleted, False otherwise.
        """
        reminder_id = self._validate_required_text(reminder_id, "reminder_id")
        conn = sqlite3.connect(self.db_path)
        try:
            cursor = conn.cursor()
            cursor.execute("DELETE FROM reminders WHERE id = ?", (reminder_id,))
            conn.commit()
            return cursor.rowcount > 0
        finally:
            conn.close()


def get_database_path() -> Path:
    """Return absolute path to `data/zenbot.db`."""
    return get_project_root() / "data" / "zenbot.db"
