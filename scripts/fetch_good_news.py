#!/usr/bin/env python3
"""Fetch uplifting-news RSS feeds and write stories.json next to this script's target.
Runs in GitHub Actions (stdlib only) and locally."""
import json, re, sys, urllib.request, html
import xml.etree.ElementTree as ET
from email.utils import parsedate_to_datetime
from datetime import datetime, timezone

FEEDS = [
    ("Good News Network", "https://www.goodnewsnetwork.org/feed/"),
    ("Positive News", "https://www.positive.news/feed/"),
    ("The Optimist Daily", "https://www.optimistdaily.com/feed/"),
    ("Reasons to be Cheerful", "https://reasonstobecheerful.world/feed/"),
]

NS = {
    "content": "http://purl.org/rss/1.0/modules/content/",
    "media": "http://search.yahoo.com/mrss/",
    "dc": "http://purl.org/dc/elements/1.1/",
}

CAT_RULES = [
    ("Animals", ["animal", "dog", "cat ", "puppy", "kitten", "zoo", "whale", "bird", "wildlife", "panda", "elephant", "horse", "pet ", "pets", "turtle", "penguin", "bear ", "deer", "fox ", "owl", "bee ", "bees", "butterfly", "species"]),
    ("Environment", ["climate", "ocean", "forest", "solar", "wind farm", "electric", "tree", "plastic", "recycl", "reef", "clean energy", "biodiversity", "river", "lake", "pollution", "carbon", "renewable", "garden", "plant ", "seed", "water quality"]),
    ("Science wins", ["research", "scientist", "study", "nasa", "space", "discover", "telescope", "vaccine", "cancer", "disease", "health", "medical", "brain", "dna", "gene", "archaeolog", "fossil", "robot", "ai ", "technology", "breakthrough", "cure", "therapy", "hospital", "doctor"]),
    ("Kindness", ["donat", "volunteer", "stranger", "rescue", "saved", "helps", "helping", "gift", "free meals", "shelter", "homeless", "teacher", "student", "school", "bakery", "neighbour", "neighbor", "community"]),
]

def clean_text(raw, limit=260):
    if not raw:
        return ""
    t = re.sub(r"<[^>]+>", " ", raw)
    t = html.unescape(t)
    t = re.sub(r"\s+", " ", t).strip()
    if len(t) > limit:
        t = t[:limit].rsplit(" ", 1)[0] + "…"
    return t

def find_image(item):
    mc = item.find("media:content", NS)
    if mc is not None and mc.get("url"):
        return mc.get("url")
    mt = item.find("media:thumbnail", NS)
    if mt is not None and mt.get("url"):
        return mt.get("url")
    enc = item.find("enclosure")
    if enc is not None and enc.get("url") and "image" in (enc.get("type") or "image"):
        return enc.get("url")
    for tag in ("content:encoded", "description"):
        el = item.find(tag, NS) if ":" in tag else item.find(tag)
        if el is not None and el.text:
            m = re.search(r'<img[^>]+src="([^"]+)"', el.text)
            if m:
                return html.unescape(m.group(1))
    return ""

def categorize(title, summary, source_default="Community"):
    text = (title + " " + summary).lower()
    for cat, keys in CAT_RULES:
        if any(k in text for k in keys):
            return cat
    return source_default

def parse_feed(source, url):
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0 (GoodNewsDaily refresher)"})
    with urllib.request.urlopen(req, timeout=30) as r:
        data = r.read()
    root = ET.fromstring(data)
    out = []
    for item in root.iter("item"):
        title = clean_text(item.findtext("title"), 300)
        link = (item.findtext("link") or "").strip()
        if not title or not link:
            continue
        desc = clean_text(item.findtext("description"))
        pub = None
        pd = item.findtext("pubDate")
        if pd:
            try:
                pub = parsedate_to_datetime(pd).astimezone(timezone.utc).isoformat()
            except Exception:
                pub = None
        words = len((desc or title).split())
        out.append({
            "title": title,
            "summary": desc,
            "link": link,
            "source": source,
            "image": find_image(item),
            "published": pub,
            "read_minutes": max(1, round(words / 180)),
            "category": categorize(title, desc),
        })
    return out

def main(out_path):
    stories, seen = [], set()
    for source, url in FEEDS:
        try:
            got = parse_feed(source, url)
            print(f"{source}: {len(got)} items")
            for s in got:
                key = s["link"].split("?")[0].lower()
                if key not in seen:
                    seen.add(key)
                    stories.append(s)
        except Exception as e:
            print(f"WARN {source} failed: {e}", file=sys.stderr)
    stories.sort(key=lambda s: s.get("published") or "", reverse=True)
    stories = stories[:40]
    payload = {"generated_at": datetime.now(timezone.utc).isoformat(), "stories": stories}
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=1)
    print(f"Wrote {len(stories)} stories to {out_path}")

if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else "stories.json")
