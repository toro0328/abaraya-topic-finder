#!/usr/bin/env python3
"""Transcribe one pre-R episode into the site's reviewable transcript format.

Audio is discovered from the legacy Seesaa RSS feed when possible. If an old
episode is no longer in the feed, pass its direct audio URL with --audio-url.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from xml.etree import ElementTree as ET

ROOT = Path(__file__).resolve().parents[1]
LEGACY_FILE = ROOT / "legacy-episodes.json"
RSS_URL = "https://abaraya204.seesaa.net/index20.rdf"
MAX_AUDIO_BYTES = 300 * 1024 * 1024
USER_AGENT = "AbabayaArchiveTranscriber/1.0 (manual GitHub Actions workflow)"


def episode_number(episode: dict) -> int | None:
    match = re.search(r"第\s*(\d+)回", str(episode.get("title", "")))
    return int(match.group(1)) if match else None


def normalize_title(value: str) -> str:
    return re.sub(r"[\s　「」『』【】［］\[\]（）()・:：!?！？]", "", value).casefold()


def rss_audio_for_episode(xml_text: str, episode: dict) -> str | None:
    """Return an enclosure URL only when the RSS item matches episode number/title."""
    wanted_no = episode_number(episode)
    wanted_title = normalize_title(str(episode.get("title", "")))
    try:
        root = ET.fromstring(xml_text)
    except ET.ParseError as exc:
        raise ValueError(f"RSS XML could not be parsed: {exc}") from exc

    for item in root.findall(".//item"):
        title = item.findtext("title") or ""
        item_no_match = re.search(r"第\s*(\d+)回", title)
        if wanted_no is not None and item_no_match and int(item_no_match.group(1)) != wanted_no:
            continue
        normalized = normalize_title(title)
        title_matches = wanted_title and (wanted_title in normalized or normalized in wanted_title)
        if not title_matches:
            continue
        enclosure = item.find("enclosure")
        url = enclosure.get("url") if enclosure is not None else None
        if url and urllib.parse.urlsplit(url).scheme == "https":
            return url
    return None


def fetch_text(url: str) -> str:
    request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(request, timeout=30) as response:
        return response.read(5 * 1024 * 1024).decode("utf-8", errors="replace")


def discover_audio(episode: dict) -> str:
    rss = fetch_text(RSS_URL)
    audio_url = rss_audio_for_episode(rss, episode)
    if not audio_url:
        no = episode_number(episode)
        raise RuntimeError(
            f"Episode {episode.get('id')} was not found in the current RSS feed. "
            "The legacy feed may only contain recent episodes; rerun with --audio-url "
            "and the episode's direct audio file URL."
        )
    return audio_url


def download_audio(url: str, destination: Path) -> None:
    parts = urllib.parse.urlsplit(url)
    if parts.scheme != "https" or not parts.hostname:
        raise ValueError("Audio URL must be an https URL.")
    request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    total = 0
    with urllib.request.urlopen(request, timeout=60) as response, destination.open("wb") as out:
        content_length = response.headers.get("Content-Length")
        if content_length and int(content_length) > MAX_AUDIO_BYTES:
            raise ValueError("Audio file exceeds the 300 MiB safety limit.")
        while True:
            chunk = response.read(1024 * 1024)
            if not chunk:
                break
            total += len(chunk)
            if total > MAX_AUDIO_BYTES:
                raise ValueError("Audio file exceeds the 300 MiB safety limit.")
            out.write(chunk)
    if total == 0:
        raise ValueError("Downloaded audio file is empty.")


def transcribe(audio_path: Path, episode: dict, audio_url: str, model_name: str) -> dict:
    try:
        from faster_whisper import WhisperModel
    except ImportError as exc:
        raise RuntimeError("Install faster-whisper from requirements-transcription.txt.") from exc

    model = WhisperModel(model_name, device="cpu", compute_type="int8")
    segments, info = model.transcribe(str(audio_path), language="ja", beam_size=5)
    rows = [
        {"start": round(float(segment.start), 2),
         "end": round(float(segment.end), 2),
         "text": segment.text.strip()}
        for segment in segments
        if segment.text.strip()
    ]
    if not rows:
        raise RuntimeError("ASR returned no speech segments; refusing to write an empty transcript.")
    return {
        "episode_id": episode["id"],
        "title": episode["title"],
        "source_url": audio_url,
        "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "language": info.language,
        "model": model_name,
        "review_status": "machine-generated-needs-review",
        "segments": rows,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--episode-id", required=True, help="Stable ID from legacy-episodes.json, e.g. legacy-134-bonus")
    parser.add_argument("--audio-url", help="Direct HTTPS audio URL; otherwise look in the legacy RSS feed")
    parser.add_argument("--model", choices=("tiny", "base", "small"), default="tiny")
    parser.add_argument("--output", type=Path, default=Path("legacy-transcripts.generated.json"))
    args = parser.parse_args()

    try:
        episodes = json.loads(LEGACY_FILE.read_text(encoding="utf-8"))
        episode = next((ep for ep in episodes if ep.get("id") == args.episode_id), None)
        if not episode:
            raise ValueError(f"Episode ID {args.episode_id!r} is not present in legacy-episodes.json.")
        audio_url = args.audio_url or episode.get("audio") or discover_audio(episode)
        temp_audio = Path("transcription-input.audio")
        try:
            print(f"Downloading {episode['id']} audio from {urllib.parse.urlsplit(audio_url).hostname}…")
            download_audio(audio_url, temp_audio)
            result = transcribe(temp_audio, episode, audio_url, args.model)
        finally:
            temp_audio.unlink(missing_ok=True)

        args.output.parent.mkdir(parents=True, exist_ok=True)
        existing = json.loads(args.output.read_text(encoding="utf-8")) if args.output.exists() else {}
        existing[episode["id"]] = result
        args.output.write_text(json.dumps(existing, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        print(f"Wrote {len(result['segments'])} timestamped segments for {episode['id']} to {args.output}.")
        print("This is an automatic draft. Review names, punctuation, and recognition errors before publishing.")
        return 0
    except (OSError, ValueError, RuntimeError, urllib.error.URLError) as exc:
        print(f"Transcription failed: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
