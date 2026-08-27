"""
Unit tests for pure business logic in services.py
Fast — no database, no HTTP, no server needed.
Bare imports — run from inside app/.
"""
import unittest
from datetime import date, timedelta

from services import (
    calculate_days,
    validate_leave_request,
    calculate_lop,
    MAX_CONSECUTIVE_DAYS,
)


class TestCalculateDays(unittest.TestCase):

    def test_inclusive_day_count(self):
        # ARRANGE
        start, end = date(2026, 8, 10), date(2026, 8, 12)
        # ACT
        days = calculate_days(start, end)
        # ASSERT
        self.assertEqual(days, 3)

    def test_single_day_leave(self):
        days = calculate_days(date(2026, 8, 10), date(2026, 8, 10))
        self.assertEqual(days, 1)

    def test_end_before_start_raises(self):
        with self.assertRaises(ValueError):
            calculate_days(date(2026, 8, 20), date(2026, 8, 10))


class TestValidateLeaveRequest(unittest.TestCase):

    def test_valid_request_returns_days(self):
        days = validate_leave_request(date(2026, 9, 1), date(2026, 9, 3))
        self.assertEqual(days, 3)

    def test_exceeds_max_consecutive_days_raises(self):
        start = date(2026, 9, 1)
        end = start + timedelta(days=MAX_CONSECUTIVE_DAYS)
        with self.assertRaises(ValueError):
            validate_leave_request(start, end)

    def test_end_before_start_raises(self):
        with self.assertRaises(ValueError):
            validate_leave_request(date(2026, 9, 10), date(2026, 9, 1))


class TestCalculateLOP(unittest.TestCase):

    def test_enough_balance_no_lop(self):
        paid, lop = calculate_lop(requested_days=3, available_days=10)
        self.assertEqual(paid, 3)
        self.assertEqual(lop, 0)

    def test_insufficient_balance_creates_lop(self):
        paid, lop = calculate_lop(requested_days=5, available_days=2)
        self.assertEqual(paid, 2)
        self.assertEqual(lop, 3)

    def test_zero_balance_all_lop(self):
        paid, lop = calculate_lop(requested_days=4, available_days=0)
        self.assertEqual(paid, 0)
        self.assertEqual(lop, 4)

    def test_exact_balance_match(self):
        paid, lop = calculate_lop(requested_days=5, available_days=5)
        self.assertEqual(paid, 5)
        self.assertEqual(lop, 0)


if __name__ == "__main__":
    unittest.main()