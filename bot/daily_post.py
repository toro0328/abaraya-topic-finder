"""Create two daily X posts from the podcast episode archive."""
from __future__ import annotations

import base64
import gzip
import json
import os
import random
import re
import sys
import time
import unicodedata
from datetime import date, datetime
from pathlib import Path
from typing import Any, Callable
from zoneinfo import ZoneInfo
from urllib.parse import urlsplit

ROOT = Path(__file__).resolve().parents[1]
MAX_WEIGHTED_LENGTH = 280
HASHTAG_START = date(2026, 10, 13)
HASHTAG_END = date(2026, 10, 19)
CAMPAIGN_HASHTAG = "#あばらや"
URL_RE = re.compile(r"https?://\S+")


def load_episodes(root: Path = ROOT) -> list[dict[str, Any]]:
    """Load current R episodes and the pre-R archive."""
    packed = (root / "archive.json.gz.b64").read_text(encoding="utf-8").strip()
    archive = json.loads(gzip.decompress(base64.b64decode(packed)))
    episodes = list(archive.get("episodes", []))
    legacy_path = root / "legacy-episodes.json"
    if legacy_path.exists():
        episodes.extend(json.loads(legacy_path.read_text(encoding="utf-8")))

    # Avoid duplicates if an episode appears in both archive sources.
    unique: dict[str, dict[str, Any]] = {}
    for episode in episodes:
        key = str(episode.get("id") or episode.get("url") or episode.get("title"))
        unique[key] = episode
    return list(unique.values())


def weighted_length(text: str) -> int:
    """Approximate X's 280-character limit (URLs count as 23)."""
    total = 0
    cursor = 0
    for match in URL_RE.finditer(text):
        total += sum(2 if unicodedata.east_asian_width(ch) in "WF" else 1
                     for ch in text[cursor:match.start()])
        total += 23
        cursor = match.end()
    total += sum(2 if unicodedata.east_asian_width(ch) in "WF" else 1
                 for ch in text[cursor:])
    return total


def episode_label(episode: dict[str, Any]) -> str:
    return "旧" if episode.get("era") == "pre-r" else "R"


def format_post(heading: str, episode: dict[str, Any], hashtag: str = "") -> str:
    title = str(episode.get("title") or "タイトル不明")
    url = str(episode.get("url") or "")
    label = episode_label(episode)
    def render(candidate: str) -> str:
        return f"{heading}\n【{label}】{candidate}\n{url}".rstrip() + (f"\n{hashtag}" if hashtag else "")

    if weighted_length(render(title)) <= MAX_WEIGHTED_LENGTH:
        return render(title)

    # Keep the post readable if a title is unusually long.
    low, high = 0, len(title)
    while low < high:
        mid = (low + high + 1) // 2
        if weighted_length(render(title[:mid] + "…")) <= MAX_WEIGHTED_LENGTH:
            low = mid
        else:
            high = mid - 1
    return render(title[:low] + "…")


def choose_daily_posts(episodes: list[dict[str, Any]], today: date, hashtag: str = "") -> tuple[str, str]:
    """Return the date-based post and a separate, distinct random post."""
    rng = random.Random(today.isoformat())
    ordered = sorted(episodes, key=lambda item: str(item.get("id") or item.get("url") or ""))
    if not ordered:
        raise ValueError("The episode archive is empty.")

    matches = []
    for episode in ordered:
        raw_date = episode.get("date")
        if not raw_date:
            continue
        try:
            published = date.fromisoformat(str(raw_date))
        except ValueError:
            continue
        if (published.month, published.day) == (today.month, today.day):
            matches.append(episode)

    available = list(ordered)
    if matches:
        daily_episode = rng.choice(matches)
        heading = f"📅 {today.month}月{today.day}日と同じ日に配信された回"
    else:
        daily_episode = rng.choice(available)
        heading = (f"📅 {today.month}月{today.day}日に配信された回は"
                   f"見つかりませんでした。代わりに今日の1本")
    available.remove(daily_episode)
    date_post = format_post(heading, daily_episode, hashtag)

    random_episode = rng.choice(available or ordered)
    random_post = format_post("🎲 今日のランダムあばらや", random_episode, hashtag)
    return date_post, random_post


def post_to_x(text: str) -> dict[str, Any]:
    """Publish a post using X API v2 with OAuth 1.0a user credentials."""
    try:
        import requests
        from requests_oauthlib import OAuth1
    except ImportError as exc:
        raise RuntimeError("Install bot/requirements.txt before posting.") from exc

    keys = {
        "client_key": os.environ.get("X_API_KEY"),
        "client_secret": os.environ.get("X_API_SECRET"),
        "resource_owner_key": os.environ.get("X_ACCESS_TOKEN"),
        "resource_owner_secret": os.environ.get("X_ACCESS_TOKEN_SECRET"),
    }
    missing = [name for name, value in keys.items() if not value]
    if missing:
        raise RuntimeError("Missing X credentials: " + ", ".join(missing))

    response = requests.post(
        "https://api.x.com/2/tweets",
        json={"text": text},
        auth=OAuth1(**keys),
        timeout=30,
    )
    response.raise_for_status()
    return response.json()


def wait_until_jst(
    target: str,
    now_func: Callable[[], datetime] | None = None,
    sleep_func: Callable[[float], None] | None = None,
) -> None:
    """Wait until today's HH:MM in Japan time. If already past, continue immediately."""
    try:
        hour, minute = (int(part) for part in target.split(":"))
    except (ValueError, TypeError) as exc:
        raise ValueError("WAIT_UNTIL_JST must use HH:MM format.") from exc
    if not (0 <= hour <= 23 and 0 <= minute <= 59):
        raise ValueError("WAIT_UNTIL_JST must be a valid 24-hour time.")

    jst = ZoneInfo("Asia/Tokyo")
    now_func = now_func or (lambda: datetime.now(jst))
    sleep_func = sleep_func or time.sleep
    now = now_func().astimezone(jst)
    deadline = now.replace(hour=hour, minute=minute, second=0, microsecond=0)

    while now < deadline:
        remaining = (deadline - now).total_seconds()
        sleep_func(remaining)
        now = now_func().astimezone(jst)


def main() -> None:
    dry_run = os.environ.get("DRY_RUN", "true").lower() in {"1", "true", "yes"}
    wait_until = os.environ.get("WAIT_UNTIL_JST", "").strip()

    now = datetime.now(ZoneInfo("Asia/Tokyo")).date()
    hashtag = CAMPAIGN_HASHTAG if HASHTAG_START <= now <= HASHTAG_END else ""
    posts = choose_daily_posts(load_episodes(), now, hashtag)
    for index, text in enumerate(posts, start=1):
        if weighted_length(text) > MAX_WEIGHTED_LENGTH:
            raise ValueError(f"Post {index} exceeds X's character limit.")

    if wait_until and not dry_run:
        print(f"Waiting until {wait_until} JST before publishing.")
        wait_until_jst(wait_until)

    for index, text in enumerate(posts, start=1):
        print(f"--- Post {index} ({'preview' if dry_run else 'publishing'}) ---")
        print(text)
        if not dry_run:
            result = post_to_x(text)
            print("Published post ID:", result.get("data", {}).get("id", "unknown"))
            if index < len(posts):
                time.sleep(2)


if __name__ == "__main__":
    main()
