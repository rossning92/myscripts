import unittest
from datetime import datetime

from utils.dateutil import format_datetime, parse_datetime

YEAR = datetime.now().year


class TestParseDatetime(unittest.TestCase):
    def test_date_only(self):
        self.assertEqual(parse_datetime("6/10"), datetime(YEAR, 6, 10))

    def test_date_with_year(self):
        self.assertEqual(parse_datetime("2026/6/10"), datetime(2026, 6, 10))

    def test_date_with_dashes(self):
        self.assertEqual(parse_datetime("2026-6-10"), datetime(2026, 6, 10))

    def test_date_with_time(self):
        self.assertEqual(parse_datetime("2026/6/10 14:30"), datetime(2026, 6, 10, 14, 30))

    def test_date_with_seconds(self):
        self.assertEqual(parse_datetime("2026/6/10 14:30:45"), datetime(2026, 6, 10, 14, 30, 45))

    def test_time_with_pm(self):
        self.assertEqual(parse_datetime("6/10 2:30pm"), datetime(YEAR, 6, 10, 14, 30))

    def test_time_with_pm_no_minutes(self):
        self.assertEqual(parse_datetime("6/10 2pm"), datetime(YEAR, 6, 10, 14, 0))

    def test_time_12am_is_midnight(self):
        self.assertEqual(parse_datetime("6/10 12am"), datetime(YEAR, 6, 10, 0, 0))

    def test_relative_today(self):
        now = datetime.now()
        self.assertEqual(parse_datetime("today"), datetime(now.year, now.month, now.day))

    def test_weekday(self):
        self.assertEqual(parse_datetime("monday").weekday(), 0)

    def test_next_weekday(self):
        result = parse_datetime("next monday")
        self.assertEqual(result.weekday(), 0)
        self.assertGreater(result, datetime.now())

    def test_invalid_raises(self):
        with self.assertRaises(ValueError):
            parse_datetime("not a date")


class TestFormatDatetime(unittest.TestCase):
    def test_date_only(self):
        self.assertEqual(format_datetime(datetime(2026, 6, 10)), "06-10")

    def test_with_year(self):
        self.assertEqual(format_datetime(datetime(2026, 6, 10), show_year=True), "2026-06-10")

    def test_with_time(self):
        self.assertEqual(format_datetime(datetime(2026, 6, 10, 14, 30)), "06-10 14:30")

    def test_midnight_omits_time(self):
        self.assertEqual(format_datetime(datetime(2026, 6, 10, 0, 0)), "06-10")


if __name__ == "__main__":
    unittest.main()
