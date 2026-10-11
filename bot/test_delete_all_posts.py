import os
import unittest
from unittest.mock import Mock, patch

import delete_all_posts as cleanup


class DeletePostsTests(unittest.TestCase):
    def setUp(self):
        self.session = Mock()
        self.me = Mock()
        self.me.json.return_value = {"data": {"id": "123", "username": "oldaccount"}}
        self.page1 = Mock()
        self.page1.json.return_value = {
            "data": [{"id": "p1"}, {"id": "p2"}],
            "meta": {"next_token": "next"},
        }
        self.page2 = Mock()
        self.page2.json.return_value = {"data": [{"id": "p3"}], "meta": {}}
        self.session.get.side_effect = [self.me, self.page1, self.page2]
        self.deleted = Mock()
        self.deleted.json.return_value = {"data": {"deleted": True}}
        self.session.delete.return_value = self.deleted

    def run_main(self, args, count=""):
        env = {
            "X_API_KEY": "key",
            "X_API_SECRET": "secret",
            "X_ACCESS_TOKEN": "token",
            "X_ACCESS_TOKEN_SECRET": "token-secret",
            "CONFIRM_DELETE_COUNT": count,
        }
        with patch.dict(os.environ, env), patch.object(cleanup, "build_session", return_value=self.session), patch(
            "sys.argv", ["delete_all_posts.py", *args]
        ):
            return cleanup.main()

    def test_default_mode_previews_all_pages_without_deleting(self):
        self.assertEqual(self.run_main([]), 0)
        self.assertEqual(self.session.delete.call_count, 0)
        self.assertEqual(self.session.get.call_count, 3)

    def test_wrong_count_refuses_to_delete(self):
        self.assertEqual(self.run_main(["--delete"], count="191"), 2)
        self.assertEqual(self.session.delete.call_count, 0)

    def test_exact_count_deletes_each_returned_post(self):
        self.assertEqual(self.run_main(["--delete"], count="3"), 0)
        self.assertEqual(
            [call.args[0] for call in self.session.delete.call_args_list],
            [
                "https://api.x.com/2/tweets/p1",
                "https://api.x.com/2/tweets/p2",
                "https://api.x.com/2/tweets/p3",
            ],
        )


if __name__ == "__main__":
    unittest.main()
