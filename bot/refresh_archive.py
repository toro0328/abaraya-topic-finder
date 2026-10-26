"""Refresh the current あばらや204号室R archive from public feeds.

Keeps existing rich episode records intact, appends newly published episodes,
and best-effort enriches recent episodes with RSS audio URLs and LISTEN chapter timestamps.
"""
from __future__ import annotations
import base64, gzip, html, json, re, urllib.request
import xml.etree.ElementTree as ET
from datetime import datetime
from email.utils import parsedate_to_datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ARCHIVE = ROOT / "archive.json.gz.b64"
FEEDS = ["https://abaraya204.com/feed/","https://anchor.fm/s/15a8cbe8/podcast/rss","https://feeds.soundcloud.com/users/soundcloud:users:161303585/sounds.rss"]
LISTEN_INDEX = "https://listen.style/p/abaraya204"
UA = {"User-Agent":"Mozilla/5.0 abaraya-topic-finder/1.3"}

def text(el,names):
    for name in names:
        node=el.find(name)
        if node is not None and node.text:return node.text.strip()
    return ""
def fetch_bytes(url):
    req=urllib.request.Request(url,headers=UA)
    with urllib.request.urlopen(req,timeout=30) as r:return r.read()
def load_archive():
    return json.loads(gzip.decompress(base64.b64decode(ARCHIVE.read_text(encoding="utf-8").strip())))
def fetch_feed():
    errors=[]
    for url in FEEDS:
        try:
            root=ET.fromstring(fetch_bytes(url));items=root.findall(".//item")
            if items:return url,items
            errors.append(f"{url}: no items")
        except Exception as exc:errors.append(f"{url}: {exc}")
    raise RuntimeError("Could not load podcast feed: "+" | ".join(errors))
def item_number(item):
    m=re.search(r"第\s*(\d+)\s*回",text(item,["title"]));return int(m.group(1)) if m else None
def item_audio(item):
    enclosure=item.find("enclosure")
    return (enclosure.get("url") or "").strip() if enclosure is not None else ""
def item_to_episode(item):
    title=text(item,["title"]);url=text(item,["link"]);guid=text(item,["guid"]);raw_date=text(item,["pubDate"])
    try:date=parsedate_to_datetime(raw_date).date().isoformat()
    except Exception:date=""
    description=text(item,["description","{http://purl.org/rss/1.0/modules/content/}encoded"])
    description=html.unescape(re.sub(r"\s+"," ",re.sub(r"<[^>]+>"," ",description))).strip()
    number=item_number(item)
    if number is None:return None
    ep={"id":guid or url or title,"title":title,"url":url,"date":date,"episode":number,"description":description,"summary":description,"era":"r","chapters":[],"tags":[],"mentions":[],"corners":[]}
    audio=item_audio(item)
    if audio:ep["audio"]=audio
    return ep
def backfill_audio(episodes,items):
    by_number={e.get('episode'):e for e in episodes if e.get('episode')}
    filled=[]
    for item in items:
        number=item_number(item);audio=item_audio(item)
        ep=by_number.get(number)
        if ep is not None and audio and not ep.get('audio'):
            ep['audio']=audio;filled.append(number)
    if filled:print('RSS audio backfilled:', ','.join('#'+str(n) for n in sorted(filled)))
    return filled
def time_to_seconds(value):
    p=[int(x) for x in value.split(':')]
    return p[0]*60+p[1] if len(p)==2 else p[0]*3600+p[1]*60+p[2] if len(p)==3 else 0
def clean_visible_html(source):
    source=re.sub(r"<script[\s\S]*?</script>|<style[\s\S]*?</style>"," ",source,flags=re.I)
    source=re.sub(r"<[^>]+>","\n",source)
    return re.sub(r"[ \t]+"," ",html.unescape(source).replace('\xa0',' '))
def listen_candidates():
    try:source=fetch_bytes(LISTEN_INDEX).decode('utf-8','ignore')
    except Exception as exc:
        print(f"LISTEN index unavailable: {exc}");return []
    slugs=[]
    for slug in re.findall(r'href=["\'](?:https://listen\.style)?/p/abaraya204/([A-Za-z0-9_-]+)',source):
        if slug not in slugs:slugs.append(slug)
    return slugs[:40]
def enrich_from_listen(episodes):
    wanted={str(ep.get('episode')):ep for ep in episodes if ep.get('episode') and not ep.get('chapters')}
    if not wanted:return
    for slug in listen_candidates():
        if not wanted:break
        listen_url=f"{LISTEN_INDEX}/{slug}"
        try:visible=clean_visible_html(fetch_bytes(listen_url).decode('utf-8','ignore'))
        except Exception:continue
        m=re.search(r"第\s*(\d+)\s*回",visible)
        if not m or m.group(1) not in wanted:continue
        ep=wanted.pop(m.group(1));ep['listen']=listen_url
        toc=visible;marker=toc.find('目次')
        if marker>=0:toc=toc[marker:marker+5000]
        chapters=[];seen=set()
        for label,stamp in re.findall(r"([^\n]{2,100}?)\s+(\d{1,2}:\d{2}(?::\d{2})?)",toc):
            label=re.sub(r"\s+"," ",label).strip(' -・｜|')
            if not label or label in {'目次','サマリー'}:continue
            sec=time_to_seconds(stamp);key=(label,sec)
            if key in seen:continue
            seen.add(key);chapters.append({'title':label,'time':sec})
        if chapters:
            ep['chapters']=chapters[:30];print(f"LISTEN chapters: #{ep['episode']} {len(ep['chapters'])}")
        else:print(f"LISTEN matched but no chapters parsed: #{ep['episode']}")
def main():
    archive=load_archive();episodes=list(archive.get("episodes",[]));keys=set()
    for ep in episodes:
        for k in (ep.get("id"),ep.get("url"),ep.get("title")):
            if k:keys.add(str(k))
    feed_url,items=fetch_feed();added=[]
    for item in reversed(items):
        ep=item_to_episode(item)
        if not ep or not ep["title"]:continue
        if any(str(v) in keys for v in (ep.get("id"),ep.get("url"),ep.get("title")) if v):continue
        episodes.append(ep);added.append(ep)
        for v in (ep.get("id"),ep.get("url"),ep.get("title")):
            if v:keys.add(str(v))
    audio_filled=backfill_audio(episodes,items)
    recent_missing=sorted([e for e in episodes if e.get('era')=='r' and not e.get('chapters')],key=lambda e:e.get('date') or '',reverse=True)[:12]
    enrich_from_listen(recent_missing)
    archive["episodes"]=episodes;archive["refreshedAt"]=datetime.now().astimezone().isoformat();archive["feedUrl"]=feed_url
    raw=json.dumps(archive,ensure_ascii=False,separators=(",",":")).encode();ARCHIVE.write_text(base64.b64encode(gzip.compress(raw,mtime=0)).decode(),encoding="utf-8")
    print(json.dumps({"feed":feed_url,"added":len(added),"titles":[e["title"] for e in added],"audio_backfilled":audio_filled,"listen_enriched":[e.get('episode') for e in recent_missing if e.get('chapters')]},ensure_ascii=False))
if __name__=="__main__":main()
