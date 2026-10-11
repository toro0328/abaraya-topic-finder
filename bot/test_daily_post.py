import unittest
from datetime import date

from daily_post import choose_daily_posts, weighted_length


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

    def test_post_length_counts_urls_as_fixed_weight(self):
        self.assertEqual(weighted_length("abc https://example.com"), 27)


if __name__ == "__main__":
    unittest.main()
