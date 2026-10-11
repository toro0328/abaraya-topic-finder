"""Preview or delete all posts authored by the authenticated X account.

Default mode only lists the number of posts. Deletion requires --delete and an
exact count confirmation, so the script cannot wipe an account by accident.
"""
from __future__ import annotations

import argparse
import os
import sys
import time
from typing import Any

import requests
from requests_oauthlib import OAuth1

API = "https://api.x.com/2"


def oauth() -> OAuth1:
    values = {
        "client_key": os.environ.get("X_API_KEY"),
        "client_secret": os.environ.get("X_API_SECRET"),
        "resource_owner_key": os.environ.get("X_ACCESS_TOKEN"),
        "resource_owner_secret": os.environ.get("X_ACCESS_TOKEN_SECRET"),
    }
    missing = [key for key, value in values.items() if not value]
    if missing:
        raise RuntimeError("Missing X credentials: " + ", ".join(missing))
    return OAuth1(**values)


def get_all_posts(session: requests.Session) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    me_response = session.get(f"{API}/users/me", params={"user.fields": "id,username"}, timeout=30)
    me_response.raise_for_status()
    me = me_response.json().get("data")
    if not me or not me.get("id"):
        raise RuntimeError("X did not return the authenticated account.")
    user_id = me["id"]

    posts: list[dict[str, Any]] = []
    token = None
    while True:
        params: dict[str, Any] = {"max_results": 100, "tweet.fields": "created_at"}
        if token:
            params["pagination_token"] = token
        response = session.get(f"{API}/users/{user_id}/tweets", params=params, timeout=30)
        response.raise_for_status()
        payload = response.json()
        posts.extend(payload.get("data", []))
        token = payload.get("meta", {}).get("next_token")
        if not token:
            break
    return me, posts


def delete_post(session: requests.Session, post_id: str) -> None:
    while True:
        response = session.delete(f"{API}/tweets/{post_id}", timeout=30)
        if response.status_code == 429:
            reset_at = int(response.headers.get("x-rate-limit-reset", time.time() + 60))
            wait_seconds = max(5, reset_at - int(time.time()) + 2)
            print(f"Rate limit reached; waiting {wait_seconds}s.", flush=True)
            time.sleep(wait_seconds)
            continue
        response.raise_for_status()
        if not response.json().get("data", {}).get("deleted"):
            raise RuntimeError(f"X did not confirm deletion for post {post_id}.")
        return


def main() -> int:
    parser = argparse.ArgumentParser(description="Preview or delete all posts on the authenticated X account.")
    parser.add_argument("--delete", action="store_true", help="delete every post returned by the account timeline")
    args = parser.parse_args()

    try:
        session = requests.Session()
        session.auth = oauth()
        me, posts = get_all_posts(session)
        username = me.get("username", "unknown")
        print(f"Account: @{username}")
        print(f"Posts found: {len(posts)} (includes replies/retweets returned by X)")
        if not posts:
            print("Nothing to delete.")
            return 0

        if not args.delete:
            print("Preview only. Nothing was deleted. Re-run with --delete and CONFIRM_DELETE_COUNT set to this exact number.")
            return 0

        expected = os.environ.get("CONFIRM_DELETE_COUNT", "")
        if expected != str(len(posts)):
            print(
                f"Refusing deletion: set CONFIRM_DELETE_COUNT={len(posts)} to match the current count.",
                file=sys.stderr,
            )
            return 2

        print(f"Deleting {len(posts)} posts from @{username}.")
        for index, post in enumerate(posts, start=1):
            delete_post(session, post["id"])
            print(f"Deleted {index}/{len(posts)}", flush=True)
        print("Deletion complete.")
        return 0
    except Exception as exc:
        print(f"Stopped: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
