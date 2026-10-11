"""Check X's public Post: Create price and alert only when it rises."""
from __future__ import annotations

import json
import os
import re
import sys
from decimal import Decimal, InvalidOperation
from html.parser import HTMLParser
from pathlib import Path
from urllib.request import Request, urlopen

PRICING_URL = "https://developer.x.com/"
ROOT = Path(__file__).resolve().parent
STATE_PATH = Path(os.environ.get("PRICE_STATE_PATH", ROOT / "baseline.json"))


class _VisibleText(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.parts: list[str] = []

    def handle_data(self, data: str) -> None:
        if data.strip():
            self.parts.append(data.strip())


def parse_post_create_price(html: str) -> Decimal:
    """Extract the first explicitly per-request USD rate under Post: Create."""
    parser = _VisibleText()
    parser.feed(html)
    text = " ".join(parser.parts)
    headings = list(re.finditer(r"Post:\s*Create", text, flags=re.IGNORECASE))
    for heading in headings:
        tail = text[heading.end():heading.end() + 800]
        boundary = re.search(
            r"(?:Content:\s*Create|Article:\s*Draft|Article:\s*Publish|Estimated Monthly Total)",
            tail,
            flags=re.IGNORECASE,
        )
        if boundary:
            tail = tail[:boundary.start()]
        rate = re.search(r"\$\s*([0-9]+(?:\.[0-9]+)?)\s*per request", tail, flags=re.IGNORECASE)
        if rate:
            try:
                return Decimal(rate.group(1))
            except InvalidOperation:
                break
    raise ValueError("Could not safely identify the Post: Create USD/request price.")


def fetch_price() -> Decimal:
    request = Request(PRICING_URL, headers={"User-Agent": "abaraya-api-price-watch/1.0"})
    with urlopen(request, timeout=30) as response:
        html = response.read().decode("utf-8", errors="replace")
    return parse_post_create_price(html)


def load_previous_price(path: Path = STATE_PATH) -> Decimal:
    data = json.loads(path.read_text(encoding="utf-8"))
    return Decimal(str(data["post_create_usd_per_request"]))


def save_price(price: Decimal, path: Path = STATE_PATH) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps({"post_create_usd_per_request": str(price)}, indent=2) + "\n",
        encoding="utf-8",
    )


def make_alert(previous: Decimal, current: Decimal) -> str:
    return (
        "【X API料金値上げ】\n"
        f"投稿作成料金が1回 ${previous} から ${current} に上がりました。\n"
        f"公式料金表: {PRICING_URL}"
    )


def post_to_x(text: str) -> None:
    import requests
    from requests_oauthlib import OAuth1

    keys = {
        "consumer_key": os.environ.get("X_API_KEY"),
        "consumer_secret": os.environ.get("X_API_SECRET"),
        "resource_owner_key": os.environ.get("X_ACCESS_TOKEN"),
        "resource_owner_secret": os.environ.get("X_ACCESS_TOKEN_SECRET"),
    }
    missing = [key for key, value in keys.items() if not value]
    if missing:
        raise RuntimeError("Missing X credentials: " + ", ".join(missing))
    response = requests.post(
        "https://api.x.com/2/tweets",
        json={"text": text},
        auth=OAuth1(**keys),
        timeout=30,
    )
    response.raise_for_status()


def main() -> int:
    dry_run = os.environ.get("DRY_RUN", "true").lower() in {"1", "true", "yes"}
    try:
        previous = load_previous_price()
        current = fetch_price()
        print(f"Post: Create price: ${previous} -> ${current} per request")
        if current == previous:
            print("No change; no post.")
            return 0
        if current < previous:
            print("Price decreased; updating baseline without posting.")
            if not dry_run:
                save_price(current)
            return 0
        message = make_alert(previous, current)
        if dry_run:
            print("Increase found; preview only, nothing posted or saved.")
            print(message)
            return 0
        post_to_x(message)
        save_price(current)
        print("Price increase alert posted; baseline updated.")
        return 0
    except Exception as exc:
        print(f"Stopped safely: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
