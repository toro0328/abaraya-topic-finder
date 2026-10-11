import unittest
from decimal import Decimal

from x_api_price_watch import make_alert, parse_post_create_price


class PricingWatchTests(unittest.TestCase):
    def test_extracts_post_create_rate_not_other_resource_rates(self):
        html = """
        <table>
          <tr><td>Posts: Read</td><td>$0.005</td><td>per resource</td></tr>
          <tr><td>Post: Create</td><td>Creating posts. Charged per request.</td>
          <td>$0.015</td><td>per request</td></tr>
          <tr><td>Content: Create</td><td>$0.010 per request</td></tr>
        </table>
        """
        self.assertEqual(parse_post_create_price(html), Decimal("0.015"))

    def test_fails_closed_if_official_page_format_changes(self):
        with self.assertRaises(ValueError):
            parse_post_create_price("<html><body>Post: Create $0.015</body></html>")

    def test_alert_includes_old_and_new_price_and_source(self):
        message = make_alert(Decimal("0.015"), Decimal("0.020"))
        self.assertIn("$0.015", message)
        self.assertIn("$0.020", message)
        self.assertIn("https://developer.x.com/", message)


if __name__ == "__main__":
    unittest.main()
