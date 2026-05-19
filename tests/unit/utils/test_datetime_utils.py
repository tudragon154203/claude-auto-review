import unittest
from datetime import datetime, timezone, timedelta

from claude_auto_review.timestamps import (
    parse_iso_timestamp,
    make_timezone_aware,
    hours_since,
    is_older_than_hours,
)


class TestParseIsoTimestamp(unittest.TestCase):
    def test_parses_naive_iso_string(self):
        result = parse_iso_timestamp("2024-01-01T12:00:00")
        self.assertIsInstance(result, datetime)
        self.assertEqual(result.year, 2024)
        self.assertEqual(result.month, 1)
        self.assertEqual(result.day, 1)
        self.assertEqual(result.hour, 12)

    def test_parses_iso_with_explicit_offset(self):
        result = parse_iso_timestamp("2024-01-01T12:00:00+05:30")
        self.assertIsInstance(result, datetime)
        self.assertEqual(result.tzinfo.utcoffset(result), timedelta(hours=5, minutes=30))

    def test_strips_z_suffix(self):
        result = parse_iso_timestamp("2024-01-01T12:00:00Z")
        self.assertEqual(result.tzinfo.utcoffset(result), timedelta(0))
        self.assertEqual(result.hour, 12)

    def test_z_suffix_has_same_epoch_as_utc_offset(self):
        ts = "2024-06-01T08:30:00"
        z_result = parse_iso_timestamp(ts + "Z")
        utc_result = parse_iso_timestamp(ts + "+00:00")
        self.assertEqual(z_result, utc_result)

    def test_raises_on_malformed_string(self):
        with self.assertRaises(ValueError):
            parse_iso_timestamp("not-a-timestamp")


class TestMakeTimezoneAware(unittest.TestCase):
    def test_attaches_local_timezone_to_naive_datetime(self):
        dt = datetime(2024, 1, 1, 12, 0, 0)
        result = make_timezone_aware(dt)
        self.assertIsNotNone(result.tzinfo)
        self.assertIsInstance(result, datetime)

    def test_preserves_utc_timezone_aware_datetime(self):
        dt = datetime(2024, 1, 1, 12, 0, 0, tzinfo=timezone.utc)
        result = make_timezone_aware(dt)
        self.assertIs(result, dt)
        self.assertEqual(result.tzinfo, timezone.utc)



class TestHoursSince(unittest.TestCase):
    PARANOID_TIMESTAMP = "2020-01-01T00:00:00+00:00"  # far in the past → always > 0

    def test_returns_positive_number_for_old_timestamp(self):
        hours = hours_since(self.PARANOID_TIMESTAMP)
        self.assertIsNotNone(hours)
        self.assertGreater(hours, 0)

    def test_returns_none_on_none_input(self):
        self.assertIsNone(hours_since(None))

    def test_returns_none_on_malformed_string(self):
        self.assertIsNone(hours_since("not-a-timestamp"))

    def test_returns_expected_hours_difference(self):
        now = datetime.now().astimezone()
        three_hours_ago = (now - timedelta(hours=3)).isoformat()
        result = hours_since(three_hours_ago)
        self.assertIsNotNone(result)
        self.assertAlmostEqual(result, 3.0, delta=0.05)


class TestIsOlderThanHours(unittest.TestCase):
    ANCIENT_TIMESTAMP = "2019-01-01T00:00:00+00:00"

    def test_returns_false_when_timeout_is_zero(self):
        self.assertFalse(is_older_than_hours(self.ANCIENT_TIMESTAMP, 0.0))

    def test_returns_true_when_very_old_and_timeout_is_positive(self):
        self.assertTrue(is_older_than_hours(self.ANCIENT_TIMESTAMP, 1.0))

    def test_returns_false_for_recent_timestamp_with_small_timeout(self):
        now = datetime.now().astimezone()
        five_min_ago = (now - timedelta(minutes=5)).isoformat()
        self.assertFalse(is_older_than_hours(five_min_ago, 1.0))

    def test_future_timestamp_with_positive_timeout_returns_false(self):
        future = "2999-01-01T00:00:00+00:00"
        self.assertFalse(is_older_than_hours(future, 1.0))

    def test_tiny_timeout_with_old_timestamp(self):
        now = datetime.now().astimezone()
        one_sec_ago = (now - timedelta(seconds=1)).isoformat()
        # 0.0001 hours ≈ 0.36 seconds; a 1-second-old timestamp exceeds it
        self.assertTrue(is_older_than_hours(one_sec_ago, 0.0001))

    def test_malformed_timestamp_returns_false(self):
        self.assertFalse(is_older_than_hours("garbage", 1.0))

    def test_negative_timeout_returns_false(self):
        self.assertFalse(is_older_than_hours(self.ANCIENT_TIMESTAMP, -5.0))
