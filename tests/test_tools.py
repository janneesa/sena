import tempfile
import unittest
from datetime import datetime, date, timezone, timedelta
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from zenbot.agent.tools.datetime_tool import DateTimeArgs, DateTimeTool
from zenbot.agent.tools.delete_reminder_tool import (
    DeleteConfirmation,
    DeleteReminderArgs,
    DeleteReminderTool,
    ReminderMatch,
)
from zenbot.agent.tools.list_reminders_tool import ListRemindersArgs, ListRemindersTool
from zenbot.agent.tools.set_reminder_tool import (
    ReminderConfirmation,
    ReminderRequest,
    SetReminderArgs,
    SetReminderTool,
)
from zenbot.agent.utils.datetime_utils import format_reminder_when


class TestDateTimeTool(unittest.TestCase):
    def test_run_returns_expected_keys(self):
        # Verifies datetime tool returns the standard time fields.
        tool = DateTimeTool()
        result = tool.run(DateTimeArgs())
        for key in ["iso", "date", "time", "timestamp", "timezone"]:
            self.assertIn(key, result)


class TestListRemindersTool(unittest.TestCase):
    def test_run_empty_returns_message(self):
        # Verifies list tool returns a friendly empty-state response.
        with tempfile.TemporaryDirectory() as tmp, patch(
            "zenbot.agent.tools.list_reminders_tool.get_database_path",
            return_value=Path(tmp) / "test.db",
        ):
            tool = ListRemindersTool()
            result = tool.run(ListRemindersArgs())

        self.assertTrue(result["success"])
        self.assertEqual(result["count"], 0)

    def test_format_when_for_display_today_tomorrow_weekday(self):
        # Verifies reminder labels render as Today/Tomorrow/Weekday with 24-hour time.
        with tempfile.TemporaryDirectory() as tmp, patch(
            "zenbot.agent.tools.list_reminders_tool.get_database_path",
            return_value=Path(tmp) / "test.db",
        ):
            tool = ListRemindersTool()

            tz_plus_two = timezone(timedelta(hours=2))
            now = datetime(2026, 2, 19, 8, 0, tzinfo=tz_plus_two)
            today_label = tool._format_when_for_display("2026-02-19T16:45:00+02:00", now=now)
            tomorrow_label = tool._format_when_for_display("2026-02-20T09:12:00+02:00", now=now)
            weekday_label = tool._format_when_for_display("2026-02-21T11:30:00+02:00", now=now)

        self.assertEqual(today_label, "Today at 16:45")
        self.assertEqual(tomorrow_label, "Tomorrow at 09:12")
        self.assertEqual(weekday_label, "Saturday at 11:30")


class TestDateTimeUtils(unittest.TestCase):
    def test_format_reminder_when_invalid_passthrough(self):
        # Verifies invalid datetime values are returned unchanged.
        value = "not-a-datetime"
        self.assertEqual(format_reminder_when(value), value)


class TestSetReminderTool(unittest.TestCase):
    def _settings(self):
        return SimpleNamespace(llm=SimpleNamespace(model="qwen", think=False))

    def test_run_success(self):
        # Verifies set-reminder workflow: extract, parse, resolve, combine, save, confirm.
        with tempfile.TemporaryDirectory() as tmp, patch(
            "zenbot.agent.tools.set_reminder_tool.get_database_path",
            return_value=Path(tmp) / "test.db",
        ):
            tool = SetReminderTool()
            tool.settings = self._settings()

            with patch.object(
                SetReminderTool,
                "_extract_reminder_request",
                return_value=ReminderRequest(task="drink water", time="9:15", intended_date="today", notes=None),
            ), patch.object(
                SetReminderTool,
                "_build_confirmation",
                return_value="Got it! I set a reminder to drink water on 18.02.2026 at 09:15",
            ):
                result = tool.run(SetReminderArgs(request="remind me to drink water today at 9:15"))

        self.assertTrue(result["success"])
        self.assertEqual(result["task"], "drink water")
        self.assertIn("reminder_id", result)
        self.assertIn("when", result)

    def test_extract_reminder_request_calls_llm_helper(self):
        # Verifies reminder extraction delegates to structured LLM helper.
        with tempfile.TemporaryDirectory() as tmp, patch(
            "zenbot.agent.tools.set_reminder_tool.get_database_path",
            return_value=Path(tmp) / "test.db",
        ), patch(
            "zenbot.agent.tools.set_reminder_tool.call_llm_with_format",
            return_value=ReminderRequest(task="drink", time="9:15", intended_date="today", notes=None),
        ) as helper_mock:
            tool = SetReminderTool()
            tool.settings = self._settings()
            res = tool._extract_reminder_request("remind me to drink at 9:15")

        self.assertIsNotNone(res)
        helper_mock.assert_called_once()

    def test_parse_time_hh_mm(self):
        # Verifies parsing of HH:MM format times.
        with tempfile.TemporaryDirectory() as tmp, patch(
            "zenbot.agent.tools.set_reminder_tool.get_database_path",
            return_value=Path(tmp) / "test.db",
        ):
            tool = SetReminderTool()
            hour, minute = tool._parse_time("9:15")
        
        self.assertEqual(hour, 9)
        self.assertEqual(minute, 15)

    def test_parse_time_with_am_pm(self):
        # Verifies parsing of time with AM/PM.
        with tempfile.TemporaryDirectory() as tmp, patch(
            "zenbot.agent.tools.set_reminder_tool.get_database_path",
            return_value=Path(tmp) / "test.db",
        ):
            tool = SetReminderTool()
            hour, minute = tool._parse_time("2:30 PM")
        
        self.assertEqual(hour, 14)
        self.assertEqual(minute, 30)

    def test_parse_time_invalid_returns_none(self):
        # Verifies invalid time strings return None.
        with tempfile.TemporaryDirectory() as tmp, patch(
            "zenbot.agent.tools.set_reminder_tool.get_database_path",
            return_value=Path(tmp) / "test.db",
        ):
            tool = SetReminderTool()
            hour, minute = tool._parse_time("invalid")
        
        self.assertIsNone(hour)
        self.assertIsNone(minute)

    def test_resolve_intended_date_today(self):
        # Verifies 'today' resolves to current date.
        with tempfile.TemporaryDirectory() as tmp, patch(
            "zenbot.agent.tools.set_reminder_tool.get_database_path",
            return_value=Path(tmp) / "test.db",
        ):
            tool = SetReminderTool()
            result = tool._resolve_intended_date("today")
            today = date.today()
        
        self.assertEqual(result, today)

    def test_resolve_intended_date_tomorrow(self):
        # Verifies 'tomorrow' resolves to next day.
        with tempfile.TemporaryDirectory() as tmp, patch(
            "zenbot.agent.tools.set_reminder_tool.get_database_path",
            return_value=Path(tmp) / "test.db",
        ):
            tool = SetReminderTool()
            result = tool._resolve_intended_date("tomorrow")
            today = date.today()
            tomorrow = date.fromordinal(today.toordinal() + 1)
        
        self.assertEqual(result, tomorrow)

    def test_resolve_intended_date_weekday(self):
        # Verifies weekday names resolve to upcoming weekday.
        with tempfile.TemporaryDirectory() as tmp, patch(
            "zenbot.agent.tools.set_reminder_tool.get_database_path",
            return_value=Path(tmp) / "test.db",
        ):
            tool = SetReminderTool()
            result = tool._resolve_intended_date("monday")
        
        self.assertIsNotNone(result)
        self.assertEqual(result.weekday(), 0)  # Monday is 0

    def test_resolve_intended_date_invalid_returns_none(self):
        # Verifies invalid date expressions return None.
        with tempfile.TemporaryDirectory() as tmp, patch(
            "zenbot.agent.tools.set_reminder_tool.get_database_path",
            return_value=Path(tmp) / "test.db",
        ):
            tool = SetReminderTool()
            result = tool._resolve_intended_date("invalid")
        
        self.assertIsNone(result)

    def test_combine_date_and_time(self):
        # Verifies date and time are combined into ISO datetime.
        with tempfile.TemporaryDirectory() as tmp, patch(
            "zenbot.agent.tools.set_reminder_tool.get_database_path",
            return_value=Path(tmp) / "test.db",
        ):
            tool = SetReminderTool()
            target_date = date(2026, 2, 18)
            iso_str = tool._combine_date_and_time(target_date, 9, 15)
        
        self.assertIsNotNone(iso_str)
        parsed = datetime.fromisoformat(iso_str)
        self.assertEqual(parsed.hour, 9)
        self.assertEqual(parsed.minute, 15)
        self.assertEqual(parsed.date(), target_date)

    def test_build_confirmation_fallback(self):
        # Verifies fallback confirmation is used when LLM confirmation fails.
        with tempfile.TemporaryDirectory() as tmp, patch(
            "zenbot.agent.tools.set_reminder_tool.get_database_path",
            return_value=Path(tmp) / "test.db",
        ), patch(
            "zenbot.agent.tools.set_reminder_tool.call_llm_with_format",
            return_value=None,
        ):
            tool = SetReminderTool()
            tool.settings = self._settings()
            message = tool._build_confirmation(
                task="drink water",
                target_date=date(2026, 2, 18),
                hour=9,
                minute=15,
            )

        self.assertIn("Reminder set", message)
        self.assertIn("drink water", message)

    def test_build_confirmation_with_llm(self):
        # Verifies LLM confirmation is used when available.
        with tempfile.TemporaryDirectory() as tmp, patch(
            "zenbot.agent.tools.set_reminder_tool.get_database_path",
            return_value=Path(tmp) / "test.db",
        ), patch(
            "zenbot.agent.tools.set_reminder_tool.call_llm_with_format",
            return_value=ReminderConfirmation(confirmation_message="Got it!"),
        ):
            tool = SetReminderTool()
            tool.settings = self._settings()
            message = tool._build_confirmation(
                task="drink water",
                target_date=date(2026, 2, 18),
                hour=9,
                minute=15,
            )

        self.assertEqual(message, "Got it!")


class TestDeleteReminderTool(unittest.TestCase):
    def _settings(self):
        return SimpleNamespace(llm=SimpleNamespace(model="qwen", think=False))

    def test_run_no_reminders_returns_error(self):
        # Verifies delete tool returns an error when there are no reminders.
        with tempfile.TemporaryDirectory() as tmp, patch(
            "zenbot.agent.tools.delete_reminder_tool.get_database_path",
            return_value=Path(tmp) / "test.db",
        ):
            tool = DeleteReminderTool()
            tool.settings = self._settings()
            result = tool.run(DeleteReminderArgs(request="delete it"))

        self.assertIn("error", result)

    def test_run_success(self):
        # Verifies delete workflow removes matched reminder and returns success payload.
        with tempfile.TemporaryDirectory() as tmp, patch(
            "zenbot.agent.tools.delete_reminder_tool.get_database_path",
            return_value=Path(tmp) / "test.db",
        ):
            tool = DeleteReminderTool()
            tool.settings = self._settings()
            created = tool.db.add_reminder("drink", "soon")

            with patch.object(
                DeleteReminderTool,
                "_match_reminder",
                return_value=ReminderMatch(reminder_id=created["id"], confidence="high", reason="match"),
            ), patch.object(
                DeleteReminderTool,
                "_build_confirmation",
                return_value="Deleted",
            ):
                result = tool.run(DeleteReminderArgs(request="delete drink reminder"))

        self.assertTrue(result["success"])
        self.assertEqual(result["deleted_reminder"]["id"], created["id"])

    def test_match_reminder_calls_llm_helper(self):
        # Verifies reminder matching delegates to structured LLM helper.
        with tempfile.TemporaryDirectory() as tmp, patch(
            "zenbot.agent.tools.delete_reminder_tool.get_database_path",
            return_value=Path(tmp) / "test.db",
        ), patch(
            "zenbot.agent.tools.delete_reminder_tool.call_llm_with_format",
            return_value=ReminderMatch(reminder_id="id1", confidence="high", reason=None),
        ) as helper_mock:
            tool = DeleteReminderTool()
            tool.settings = self._settings()
            result = tool._match_reminder("delete", [{"id": "id1", "task": "x", "when": "y"}])

        self.assertIsNotNone(result)
        helper_mock.assert_called_once()

    def test_build_confirmation_fallback(self):
        # Verifies fallback deletion confirmation text is used when LLM fails.
        with tempfile.TemporaryDirectory() as tmp, patch(
            "zenbot.agent.tools.delete_reminder_tool.get_database_path",
            return_value=Path(tmp) / "test.db",
        ), patch(
            "zenbot.agent.tools.delete_reminder_tool.call_llm_with_format",
            return_value=None,
        ):
            tool = DeleteReminderTool()
            tool.settings = self._settings()
            msg = tool._build_confirmation({"task": "x", "when": "y"})

        self.assertIn("Reminder deleted", msg)

    def test_build_confirmation_with_llm(self):
        # Verifies LLM-provided deletion confirmation is returned when available.
        with tempfile.TemporaryDirectory() as tmp, patch(
            "zenbot.agent.tools.delete_reminder_tool.get_database_path",
            return_value=Path(tmp) / "test.db",
        ), patch(
            "zenbot.agent.tools.delete_reminder_tool.call_llm_with_format",
            return_value=DeleteConfirmation(confirmation_message="Removed"),
        ):
            tool = DeleteReminderTool()
            tool.settings = self._settings()
            msg = tool._build_confirmation({"task": "x", "when": "y"})

        self.assertEqual(msg, "Removed")
