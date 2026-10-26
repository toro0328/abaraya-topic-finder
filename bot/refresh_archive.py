"""Refresh the current あばらや204号室R archive from public feeds.

Keeps existing rich episode records intact, appends newly published episodes,
and best-effort enriches new episodes with LISTEN chapter timestamps.
"""
from __future__ import annotations
import base64, gzip, html, json, re, urllib.parse, urllib.request
import xml.etree.ElementTree as ET
from datetime import datetime
from email.utils import parsedate_to_datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ARCHIVE = ROOT / "archive.json.gz.b64"
FEEDS = [
    "https://abaraya204.com/feed/",
    "https://anchor.fm/s/15a8cbe8/podcast/rss",
    "https://feeds.soundcloud.com/users/soundcloud:users:161303585/sounds.rss",
]
LISTEN_INDEX = "https://listen.style/p/abaraya204"
UA = {"User-Agent":"Mozilla/5.0 abaraya-topic-finder/1.2"}

def text(el, names):
    for name in names:
        node = el.find(name)
        if node is not None and node.text:
            return node.text.strip()
    return ""

def fetch_bytes(url):
    req=urllib.request.Request(url, headers=UA)
    with urllib.request.urlopen(req, timeout=30) as r:
        return r.read()

def load_archive():
    packed = ARCHIVE.read_text(encoding="utf-8").strip()
    return json.loads(gzip.decompress(base64.b64decode(packed)))

def fetch_feed():
    errors=[]
    for url in FEEDS:
        try:
            root=ET.fromstring(fetch_bytes(url))
            items=root.findall(".//item")
            if items:
                return url, items
            errors.append(f"{url}: no items")
        except Exception as exc:
            errors.append(f"{url}: {exc}")
    raise RuntimeError("Could not load podcast feed: " + " | ".join(errors))

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
    description=html.unescape(re.sub(r"\s+"," ",description)).strip()
    m=re.search(r"第\s*(\d+)\s*回",title)
    number=int(m.group(1)) if m else None
    if number is None:
        return None
    enclosure=item.find("enclosure")
    audio=(enclosure.get("url") or "").strip() if enclosure is not None else ""
    episode={"id": guid or url or title, "title": title, "url": url, "date": date,
             "episode": number, "description": description, "summary":description,
             "era":"r", "chapters":[], "tags":[], "mentions":[], "corners":[]}
    if audio:
        episode["audio"]=audio
    return episode

def time_to_seconds(value):
    parts=[int(x) for x in value.split(':')]
    if len(parts)==2:
        return parts[0]*60+parts[1]
    if len(parts)==3:
        return parts[0]*3600+parts[1]*60+parts[2]
    return 0

def clean_visible_html(source):
    source=re.sub(r"<script[\s\S]*?</script>|<style[\s\S]*?</style>"," ",source,flags=re.I)
    source=re.sub(r"<[^>]+>","\n",source)
    source=html.unescape(source).replace('\xa0',' ')
    return re.sub(r"[ \t]+"," ",source)

def listen_candidates():
    try:
        source=fetch_bytes(LISTEN_INDEX).decode('utf-8','ignore')
    except Exception as exc:
        print(f"LISTEN index unavailable: {exc}")
        return []
    slugs=[]
    for slug in re.findall(r'href=["\'](?:https://listen\.style)?/p/abaraya204/([A-Za-z0-9_-]+)',source):
        if slug not in slugs:
            slugs.append(slug)
    return slugs[:30]

def enrich_from_listen(episodes):
    """Match recent LISTEN pages by episode number and copy their TOC timestamps.

    LISTEN exposes a rendered 目次 on episode pages. This deliberately fails soft:
    RSS updates still succeed even if LISTEN is temporarily behind/unavailable.
    """
    if not episodes:
        return
    wanted={str(ep.get('episode')):ep for ep in episodes if ep.get('episode')}
    if not wanted:
        return
    for slug in listen_candidates():
        if not wanted:
            break
        listen_url=f"{LISTEN_INDEX}/{slug}"
        try:
            source=fetch_bytes(listen_url).decode('utf-8','ignore')
            visible=clean_visible_html(source)
        except Exception:
            continue
        m=re.search(r"第\s*(\d+)\s*回",visible)
        if not m or m.group(1) not in wanted:
            continue
        ep=wanted.pop(m.group(1))
        ep['listen']=listen_url
        # Restrict extraction to the TOC area where possible.
        toc=visible
        marker=toc.find('目次')
        if marker>=0:
            toc=toc[marker:marker+5000]
        chapters=[]
        seen=set()
        # LISTEN renders chapter label followed by mm:ss (or hh:mm:ss).
        for label,stamp in re.findall(r"([^\n]{2,100}?)\s+(\d{1,2}:\d{2}(?::\d{2})?)",toc):
            label=re.sub(r"\s+"," ",label).strip(' -・｜|')
            if not label or label in {'目次','サマリー'}:
                continue
            sec=time_to_seconds(stamp)
            key=(label,sec)
            if key in seen:
                continue
            seen.add(key)
            chapters.append({'title':label,'time':sec})
        if chapters:
            ep['chapters']=chapters[:30]
            print(f"LISTEN chapters: #{ep['episode']} {len(ep['chapters'])}")
        else:
            print(f"LISTEN matched but no chapters parsed: #{ep['episode']}")

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
        if not ep or not ep["title"]: continue
        if any(str(v) in keys for v in (ep.get("id"),ep.get("url"),ep.get("title")) if v):
            continue
        episodes.append(ep); added.append(ep)
        for v in (ep.get("id"),ep.get("url"),ep.get("title")):
            if v: keys.add(str(v))
    enrich_from_listen(added)
    archive["episodes"]=episodes
    archive["refreshedAt"]=datetime.now().astimezone().isoformat()
    archive["feedUrl"]=feed_url
    raw=json.dumps(archive,ensure_ascii=False,separators=(",",":")).encode()
    ARCHIVE.write_text(base64.b64encode(gzip.compress(raw,mtime=0)).decode(),encoding="utf-8")
    print(json.dumps({"feed":feed_url,"added":len(added),"titles":[e["title"] for e in added],
                      "listen_enriched":[e.get('episode') for e in added if e.get('chapters')]},ensure_ascii=False))

if __name__=="__main__": main()
