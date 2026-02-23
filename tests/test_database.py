import tempfile
import unittest
from pathlib import Path

from zenbot.agent.utils.database import DatabaseHelper, get_database_path


class TestDatabaseHelper(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.db_path = Path(self.tmp.name) / "test.db"
        self.db = DatabaseHelper(self.db_path)

    def tearDown(self):
        self.tmp.cleanup()

    def test_add_and_get_reminder(self):
        # Verifies a reminder can be inserted and then fetched by id.
        created = self.db.add_reminder("drink water", "in 5 minutes", notes="health")
        fetched = self.db.get_reminder(created["id"])

        self.assertIsNotNone(fetched)
        self.assertEqual(fetched["task"], "drink water")
        self.assertEqual(fetched["when"], "in 5 minutes")
        self.assertEqual(fetched["notes"], "health")

    def test_get_all_excludes_completed_by_default(self):
        # Verifies completed reminders are hidden unless explicitly requested.
        a = self.db.add_reminder("a", "soon")
        b = self.db.add_reminder("b", "later")
        self.db.mark_completed(a["id"])

        active = self.db.get_all_reminders()
        all_items = self.db.get_all_reminders(include_completed=True)

        self.assertEqual(len(active), 1)
        self.assertEqual(active[0]["id"], b["id"])
        self.assertEqual(len(all_items), 2)

    def test_mark_completed_returns_false_for_missing(self):
        # Verifies marking a missing reminder as completed returns False.
        self.assertFalse(self.db.mark_completed("missing-id"))

    def test_delete_reminder(self):
        # Verifies delete succeeds once, then fails when item no longer exists.
        item = self.db.add_reminder("task", "tomorrow")
        self.assertTrue(self.db.delete_reminder(item["id"]))
        self.assertFalse(self.db.delete_reminder(item["id"]))
        self.assertIsNone(self.db.get_reminder(item["id"]))


class TestDatabasePath(unittest.TestCase):
    def test_database_path_points_to_data_zenbot_db(self):
        # Verifies helper resolves the expected default database path.
        path = get_database_path()
        self.assertEqual(path.name, "zenbot.db")
        self.assertEqual(path.parent.name, "data")
