import unittest
from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo

from daily_post import choose_daily_posts, wait_until_jst, weighted_length


class DailyPostTests(unittest.TestCase):
    def test_matching_date_posts_that_episode_and_a_different_random_one(self):
        episodes = [
            {"id": "r", "title": "R episode", "date": "2020-05-10", "url": "https://example.com/r"},
            {"id": "old", "title": "Old episode", "date": "2015-08-01", "url": "https://example.com/old", "era": "pre-r"},
        ]
        first, second = choose_daily_posts(episodes, date(2026, 5, 10))
        self.assertIn("同じ日に配信", first)
        self.assertIn("R episode", first)
        self.assertIn("Old episode", second)
        self.assertNotEqual(first, second)

    def test_missing_date_says_none_and_includes_one_random_episode(self):
        episodes = [
            {"id": "1", "title": "One", "date": "2020-01-01", "url": "https://example.com/1"},
            {"id": "2", "title": "Two", "date": None, "url": "https://example.com/2", "era": "pre-r"},
            {"id": "3", "title": "Three", "date": None, "url": "https://example.com/3", "era": "pre-r"},
        ]
        first, second = choose_daily_posts(episodes, date(2026, 2, 3))
        self.assertIn("見つかりませんでした", first)
        self.assertIn("代わりに今日の1本", first)
        self.assertTrue(any(title in first for title in ("One", "Two", "Three")))
        self.assertTrue(any(title in second for title in ("One", "Two", "Three")))
        self.assertNotEqual(first, second)

    def test_campaign_hashtag_is_added_only_during_the_one_week_window(self):
        episodes = [
            {"id": "1", "title": "Episode", "date": "2020-01-01", "url": "https://example.com/1"},
            {"id": "2", "title": "Other", "date": "2020-01-02", "url": "https://example.com/2"},
        ]
        first, second = choose_daily_posts(episodes, date(2026, 10, 13), "#あばらや")
        self.assertTrue(first.endswith("#あばらや"))
        self.assertTrue(second.endswith("#あばらや"))
        self.assertLessEqual(weighted_length(first), 280)
        self.assertLessEqual(weighted_length(second), 280)

        first, second = choose_daily_posts(episodes, date(2026, 10, 20))
        self.assertNotIn("#あばらや", first)
        self.assertNotIn("#あばらや", second)

    def test_post_length_counts_urls_as_fixed_weight(self):
        self.assertEqual(weighted_length("abc https://example.com"), 27)


    def test_waits_until_target_in_japan_time(self):
        clock = [datetime(2026, 10, 12, 19, 59, 59, 500000, tzinfo=ZoneInfo("Asia/Tokyo"))]
        sleeps = []

        def sleep_for(seconds):
            sleeps.append(seconds)
            clock[0] += timedelta(seconds=seconds)

        wait_until_jst("20:00", now_func=lambda: clock[0], sleep_func=sleep_for)
        self.assertEqual(sleeps, [0.5])
        self.assertEqual(clock[0].strftime("%H:%M:%S"), "20:00:00")

    def test_does_not_wait_if_target_has_passed(self):
        clock = [datetime(2026, 10, 12, 20, 0, 1, tzinfo=ZoneInfo("Asia/Tokyo"))]
        sleeps = []
        wait_until_jst("20:00", now_func=lambda: clock[0], sleep_func=sleeps.append)
        self.assertEqual(sleeps, [])

    def test_rejects_invalid_wait_time(self):
        with self.assertRaises(ValueError):
            wait_until_jst("25:00", now_func=lambda: datetime.now(ZoneInfo("Asia/Tokyo")))

if __name__ == "__main__":
    unittest.main()
