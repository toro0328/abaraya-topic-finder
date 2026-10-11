import unittest

from transcribe_legacy import episode_number, normalize_title, rss_audio_for_episode


class TranscriptDiscoveryTests(unittest.TestCase):
    def setUp(self):
        self.episode = {"id": "legacy-135", "title": "第135回「最終回」"}

    def test_extracts_episode_number(self):
        self.assertEqual(episode_number(self.episode), 135)

    def test_normalizes_japanese_title_punctuation(self):
        self.assertEqual(normalize_title("第135回「最終回」"), normalize_title(" 第135回 最終回 "))

    def test_matches_rss_enclosure_by_episode_number(self):
        feed = """<rss><channel><item><title>第135回「最終回」</title>
        <enclosure url="https://cdn.example.test/episode.mp3" type="audio/mpeg"/>
        </item></channel></rss>"""
        self.assertEqual(rss_audio_for_episode(feed, self.episode), "https://cdn.example.test/episode.mp3")

    def test_does_not_match_different_episode_number(self):
        feed = """<rss><channel><item><title>第134回「最終回」</title>
        <enclosure url="https://cdn.example.test/wrong.mp3"/>
        </item></channel></rss>"""
        self.assertIsNone(rss_audio_for_episode(feed, self.episode))

    def test_ignores_non_https_enclosures(self):
        feed = """<rss><channel><item><title>第135回「最終回」</title>
        <enclosure url="http://cdn.example.test/episode.mp3"/>
        </item></channel></rss>"""
        self.assertIsNone(rss_audio_for_episode(feed, self.episode))


if __name__ == "__main__":
    unittest.main()
