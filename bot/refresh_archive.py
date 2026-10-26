"""Refresh the current あばらや204号室R archive from its public RSS feed.

Keeps existing rich episode records intact and appends newly published episodes.
"""
from __future__ import annotations
import base64, gzip, json, re, urllib.request
import xml.etree.ElementTree as ET
from datetime import datetime
from email.utils import parsedate_to_datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ARCHIVE = ROOT / "archive.json.gz.b64"
FEEDS = [
    "https://anchor.fm/s/15a8cbe8/podcast/rss",
    "https://feeds.soundcloud.com/users/soundcloud:users:161303585/sounds.rss",
]

def text(el, names):
    for name in names:
        node = el.find(name)
        if node is not None and node.text:
            return node.text.strip()
    return ""

def load_archive():
    packed = ARCHIVE.read_text(encoding="utf-8").strip()
    return json.loads(gzip.decompress(base64.b64decode(packed)))

def fetch_feed():
    last = None
    for url in FEEDS:
        try:
            req=urllib.request.Request(url, headers={"User-Agent":"abaraya-topic-finder/1.0"})
            with urllib.request.urlopen(req, timeout=30) as r:
                body=r.read()
            root=ET.fromstring(body)
            items=root.findall(".//item")
            if items:
                return url, items
        except Exception as exc:
            last=exc
    raise RuntimeError(f"Could not load podcast RSS: {last}")

def item_to_episode(item):
    title=text(item,["title"])
    url=text(item,["link"])
    guid=text(item,["guid"])
    raw_date=text(item,["pubDate"])
    try:
        date=parsedate_to_datetime(raw_date).date().isoformat()
    except Exception:
        date=""
    description=text(item,["description","{http://purl.org/rss/1.0/modules/content/}encoded"])
    description=re.sub(r"<[^>]+>"," ",description)
    description=re.sub(r"\s+"," ",description).strip()
    m=re.search(r"第\s*(\d+)\s*回",title)
    number=int(m.group(1)) if m else None
    return {"id": guid or url or title, "title": title, "url": url, "date": date,
            "episode": number, "description": description, "era":"r"}

def main():
    archive=load_archive()
    episodes=list(archive.get("episodes",[]))
    keys=set()
    for ep in episodes:
        for k in (ep.get("id"),ep.get("url"),ep.get("title")):
            if k: keys.add(str(k))
    feed_url, items=fetch_feed()
    added=[]
    for item in reversed(items):
        ep=item_to_episode(item)
        if not ep["title"]: continue
        if any(str(v) in keys for v in (ep.get("id"),ep.get("url"),ep.get("title")) if v):
            continue
        episodes.append(ep); added.append(ep)
        for v in (ep.get("id"),ep.get("url"),ep.get("title")):
            if v: keys.add(str(v))
    archive["episodes"]=episodes
    archive["refreshedAt"]=datetime.now().astimezone().isoformat()
    archive["feedUrl"]=feed_url
    raw=json.dumps(archive,ensure_ascii=False,separators=(",",":")).encode()
    ARCHIVE.write_text(base64.b64encode(gzip.compress(raw,mtime=0)).decode(),encoding="utf-8")
    print(json.dumps({"added":len(added),"titles":[e["title"] for e in added]},ensure_ascii=False))

if __name__=="__main__": main()
