import unittest

from app.accounting.journal_service import _lock_source_journal_identity


class FakeCursor:
    def __init__(self, existing=None):
        self.existing = existing
        self.calls = []

    def execute(self, sql, params=None):
        self.calls.append((sql, params))

    def fetchone(self):
        return self.existing


class TestSourceJournalIdempotency(unittest.TestCase):
    def test_manual_journal_does_not_take_source_lock(self):
        cursor = FakeCursor()
        _lock_source_journal_identity(cursor, 1, None, None, None)
        self.assertEqual(cursor.calls, [])

    def test_source_identity_is_locked_and_checked(self):
        cursor = FakeCursor()
        _lock_source_journal_identity(cursor, 1, "inventory", "stock_document", 42)
        self.assertEqual(len(cursor.calls), 2)
        self.assertIn("pg_advisory_xact_lock", cursor.calls[0][0])
        self.assertEqual(cursor.calls[1][1], (1, "INVENTORY", "STOCK_DOCUMENT", 42))

    def test_existing_source_journal_blocks_duplicate(self):
        cursor = FakeCursor({
            "id": 9,
            "journal_no": "GJ-000009",
            "status": "DRAFT",
        })
        with self.assertRaisesRegex(ValueError, "GJ-000009.*DRAFT"):
            _lock_source_journal_identity(cursor, 1, "INVENTORY", "STOCK_DOCUMENT", 42)

    def test_source_type_required(self):
        cursor = FakeCursor()
        with self.assertRaisesRegex(ValueError, "required"):
            _lock_source_journal_identity(cursor, 1, "INVENTORY", "", 42)
        self.assertEqual(cursor.calls, [])


if __name__ == "__main__":
    unittest.main()