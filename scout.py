#!/usr/bin/env python3
"""Fetch free public trend signals and write data/trends.json (stdlib only).

Sources (no keys, no signup):
  - Reddit r/personalfinance and r/financialindependence hot posts (public .json)
  - Google News RSS search for personal finance topics

On any source failure the error is recorded and the run continues; if every
source fails and an old trends file exists, the old file is kept untouched.
"""
import json
import re
import sys
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

ROOT = Path(__file__).resolve().parent
DATA_DIR = ROOT / "data"
TRENDS_FILE = DATA_DIR / "trends.json"

UA = "IncomeBuilding/1.0 (+https://github.com/honeybbear/income-building)"

STOPWORDS = set(
    "the a an and or of to in on for with is are was were be been being at as by "
    "from that this it its it’s it's you your he she they them we our us i me my "
    "not no do does did don doesn didn can could should would will just how what "
    "when where why which who whom whose there their then than so such only also "
    "into out up down over under about into vs via per new get got getting make "
    "made like than too very".split()
)

QUESTION_STARTS = re.compile(
    r"^(how|what|why|when|where|should|can|could|is|are|do|does|did|would|any|has|have)\b",
    re.IGNORECASE,
)


def fetch_json(url, timeout=20):
    req = Request(url, headers={"User-Agent": UA})
    with urlopen(req, timeout=timeout) as resp:
        return json.loads(resp.read().decode("utf-8", errors="replace"))


def fetch_reddit(sub, limit=20):
    data = fetch_json("https://www.reddit.com/r/%s/hot.json?limit=%d" % (sub, limit))
    posts = []
    for child in data.get("data", {}).get("children", []):
        d = child.get("data", {})
        posts.append(
            {
                "title": d.get("title", ""),
                "score": d.get("score", 0),
                "comments": d.get("num_comments", 0),
                "url": "https://www.reddit.com" + d.get("permalink", ""),
                "source": "r/" + sub,
            }
        )
    return posts


def fetch_gnews(query, limit=15):
    q = query.replace(" ", "+")
    url = (
        "https://news.google.com/rss/search?q=%s&hl=en-US&gl=US&ceid=US:en" % q
    )
    req = Request(url, headers={"User-Agent": UA})
    with urlopen(req, timeout=20) as resp:
        root = ET.fromstring(resp.read())
    items = []
    for item in list(root.iter("item"))[:limit]:
        src_el = item.find("source")
        items.append(
            {
                "title": (item.findtext("title") or "").strip(),
                "link": (item.findtext("link") or "").strip(),
                "published": (item.findtext("pubDate") or "").strip(),
                "source": (src_el.text or "").strip() if src_el is not None else "",
            }
        )
    return items


def top_keywords(titles, n=12):
    freq = {}
    for t in titles:
        for w in re.findall(r"[a-z]{3,}", t.lower()):
            if w not in STOPWORDS:
                freq[w] = freq.get(w, 0) + 1
    ranked = sorted(freq.items(), key=lambda kv: kv[1], reverse=True)[:n]
    return [{"keyword": k, "mentions": c} for k, c in ranked]


def main():
    errors = []
    reddit_posts = []
    for sub in ("personalfinance", "financialindependence"):
        try:
            reddit_posts.extend(fetch_reddit(sub))
        except (URLError, HTTPError, ValueError, KeyError) as e:
            errors.append("reddit r/%s: %s" % (sub, e))

    news_items = []
    for query in ("personal finance", "budgeting tips", "saving money"):
        try:
            news_items.extend(fetch_gnews(query, limit=8))
        except (URLError, HTTPError, ET.ParseError, ValueError) as e:
            errors.append("google news '%s': %s" % (query, e))

    if not reddit_posts and not news_items:
        msg = "All trend sources failed: %s" % "; ".join(errors)
        if TRENDS_FILE.exists():
            print(msg + " -- keeping previous trends file.", file=sys.stderr)
            return 0
        print(msg, file=sys.stderr)
        return 1

    titles = [p["title"] for p in reddit_posts] + [n["title"] for n in news_items]

    questions = []
    for p in reddit_posts:
        t = p["title"].strip()
        if t.endswith("?") or QUESTION_STARTS.match(t):
            questions.append(p)
    questions.sort(key=lambda p: p["comments"], reverse=True)

    highlights = sorted(reddit_posts, key=lambda p: p["score"], reverse=True)[:10]

    payload = {
        "fetched_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "sources": [
            "Reddit r/personalfinance + r/financialindependence (public JSON)",
            "Google News RSS (personal finance searches)",
        ],
        "topics": top_keywords(titles),
        "questions": questions[:12],
        "discussion_highlights": [
            {
                "title": p["title"],
                "source": p["source"],
                "url": p["url"],
                "score": p["score"],
                "comments": p["comments"],
            }
            for p in highlights
        ],
        "news": news_items[:15],
        "errors": errors,
    }
    DATA_DIR.mkdir(exist_ok=True)
    TRENDS_FILE.write_text(
        json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )
    print(
        "Wrote %s: %d reddit posts, %d news items, %d errors."
        % (TRENDS_FILE, len(reddit_posts), len(news_items), len(errors))
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
