"""Datetime parsing and calculation utilities for reminders."""

from __future__ import annotations

import re
from datetime import datetime, timedelta, timezone, date


def parse_time_string(time_str: str) -> tuple[int | None, int | None]:
    """Parse time string (e.g., '9:15', '9:15 AM', '3:45 PM', '14:30') to (hour, minute).
    
    Handles both 12-hour format with AM/PM and 24-hour format.
    
    Args:
        time_str: The time string to parse.
    
    Returns:
        (hour, minute) tuple with hour in 24-hour format, or (None, None) if parsing fails.
        Hour range: 0-23. Minute range: 0-59.
    """
    text = time_str.strip().lower()

    # Try regex: HH:MM with optional AM/PM
    match = re.search(r"(\d{1,2}):(\d{2})\s*(am|pm)?", text)
    if not match:
        return None, None

    hour = int(match.group(1))
    minute = int(match.group(2))
    meridiem = (match.group(3) or "").lower()

    # Validate minute
    if minute < 0 or minute > 59:
        return None, None

    # Handle AM/PM
    if meridiem:
        if hour < 1 or hour > 12:
            return None, None
        if meridiem == "pm" and hour != 12:
            hour += 12
        if meridiem == "am" and hour == 12:
            hour = 0
    else:
        # 24-hour format
        if hour < 0 or hour > 23:
            return None, None

    return hour, minute


def resolve_date_expression(expression: str) -> date | None:
    """Resolve a date expression ('today', 'tomorrow', 'monday', etc.) to an actual date.
    
    Args:
        expression: The date expression to resolve (case-insensitive).
    
    Returns:
        datetime.date object, or None if the expression is invalid.
    """
    text = expression.strip().lower()
    now_local = datetime.now().astimezone()
    today = now_local.date()

    if text == "today":
        return today

    if text == "tomorrow":
        return today + timedelta(days=1)

    # Map weekday names to their numeric value (0=Monday, 6=Sunday)
    weekday_map = {
        "monday": 0,
        "tuesday": 1,
        "wednesday": 2,
        "thursday": 3,
        "friday": 4,
        "saturday": 5,
        "sunday": 6,
    }

    if text in weekday_map:
        target_weekday = weekday_map[text]
        current_weekday = today.weekday()

        # Calculate days until the target weekday
        days_ahead = (target_weekday - current_weekday) % 7

        # If it's 0, the weekday is today; shift to next week
        if days_ahead == 0:
            days_ahead = 7

        return today + timedelta(days=days_ahead)

    return None


def combine_date_and_time(target_date: date, hour: int, minute: int) -> str:
    """Combine a date and time into an ISO-8601 timestamp with local timezone.
    
    Args:
        target_date: The date to use.
        hour: Hour in 24-hour format (0-23).
        minute: Minute (0-59).
    
    Returns:
        ISO-8601 datetime string with local timezone awareness.
        
    Example:
        >>> combine_date_and_time(date(2026, 2, 18), 9, 15)
        '2026-02-18T09:15:00+05:30'  # Example with IST timezone
    """
    now_local = datetime.now().astimezone()
    due_local = datetime(
        target_date.year,
        target_date.month,
        target_date.day,
        hour,
        minute,
        tzinfo=now_local.tzinfo,
    )
    return due_local.isoformat()


def parse_iso_datetime(value: str) -> datetime | None:
    """Parse an ISO-8601 datetime string.
    
    Args:
        value: The ISO datetime string.
    
    Returns:
        datetime object with timezone, or None if parsing fails.
    """
    try:
        parsed = datetime.fromisoformat(value)
        return parsed
    except (ValueError, TypeError):
        return None


def is_datetime_past(iso_datetime: str) -> bool:
    """Check if an ISO-8601 datetime is in the past (relative to current UTC time).
    
    Args:
        iso_datetime: The ISO-8601 datetime string to check.
    
    Returns:
        True if the datetime is in the past, False otherwise or on parse error.
    """
    dt = parse_iso_datetime(iso_datetime)
    if dt is None:
        return False
    
    # Ensure it has timezone info
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    
    now = datetime.now(timezone.utc)
    return dt <= now


def format_reminder_when(iso_datetime: str, now: datetime | None = None) -> str:
    """Format reminder datetime into a human-readable local label.

    Output format:
    - "Today at HH:MM"
    - "Tomorrow at HH:MM"
    - "Weekday at HH:MM"

    Args:
        iso_datetime: ISO-8601 datetime string.
        now: Optional reference datetime for deterministic testing.

    Returns:
        Human-readable label, or the original input if parsing fails.
    """
    parsed = parse_iso_datetime(iso_datetime)
    if parsed is None:
        return iso_datetime

    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)

    local_dt = parsed.astimezone()

    if now is None:
        now_local = datetime.now().astimezone()
    else:
        if now.tzinfo is None:
            now = now.replace(tzinfo=local_dt.tzinfo)
        now_local = now.astimezone(local_dt.tzinfo)

    today = now_local.date()
    target_date = local_dt.date()

    if target_date == today:
        day_label = "Today"
    elif target_date == today + timedelta(days=1):
        day_label = "Tomorrow"
    else:
        day_label = local_dt.strftime("%A")

    return f"{day_label} at {local_dt.strftime('%H:%M')}"
