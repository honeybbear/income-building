#!/usr/bin/env python3
"""Fetch free public trend signals and write data/trends.json (stdlib only).

Sources (no keys, no signup):
  - Reddit r/personalfinance and r/financialindependence hot posts (public .json)
  - Google News RSS search for personal finance topics
  - Hacker News top stories filtered by finance keywords (public Firebase API)
  - Google Trends US daily trending searches filtered by finance keywords (RSS)

Every source is optional: on failure the error is recorded and the run
continues. If every source fails and an old trends file exists, the old file
is kept untouched. Topics are deduped across sources by normalized title and
each item carries per-source attribution.
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

FINANCE_KW = {
    "money", "finance", "financial", "budget", "budgeting", "save", "saving",
    "savings", "invest", "investing", "investment", "debt", "credit", "loan",
    "mortgage", "rent", "retirement", "401k", "ira", "tax", "taxes", "salary",
    "wage", "income", "expense", "expenses", "bank", "banking", "interest",
    "inflation", "recession", "stock", "stocks", "etf", "insurance", "bill",
    "bills", "frugal", "coupon", "coupons", "side hustle", "emergency fund",
}


def is_finance(text):
    t = text.lower()
    return any(re.search(r"\b" + re.escape(k) + r"\b", t) for k in FINANCE_KW)


def norm_title(t):
    return re.sub(r"\s+", " ", re.sub(r"[^a-z0-9 ]", "", t.lower())).strip()


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
    url = "https://news.google.com/rss/search?q=%s&hl=en-US&gl=US&ceid=US:en" % q
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
                "source": (src_el.text or "").strip() if src_el is not None else "Google News",
            }
        )
    return items


def fetch_hn(top_n=40):
    """Hacker News top stories via the public Firebase API, finance-filtered."""
    ids = fetch_json("https://hacker-news.firebaseio.com/v0/topstories.json")
    stories = []
    for sid in ids[:top_n]:
        try:
            it = fetch_json(
                "https://hacker-news.firebaseio.com/v0/item/%s.json" % sid,
                timeout=10,
            )
        except (URLError, HTTPError, ValueError):
            continue
        title = it.get("title", "") or ""
        if it.get("type") != "story" or not is_finance(title):
            continue
        stories.append(
            {
                "title": title,
                "url": it.get("url")
                or "https://news.ycombinator.com/item?id=%s" % sid,
                "score": it.get("score", 0),
                "comments": it.get("descendants", 0),
                "source": "Hacker News",
            }
        )
    return stories


def fetch_gtrends_us():
    """Google Trends US daily trending searches, finance-filtered."""
    req = Request(
        "https://trends.google.com/trending/rss?geo=US", headers={"User-Agent": UA}
    )
    with urlopen(req, timeout=20) as resp:
        root = ET.fromstring(resp.read())
    terms = []
    for item in root.iter("item"):
        title = (item.findtext("title") or "").strip()
        if title and is_finance(title):
            terms.append({"term": title, "source": "Google Trends US"})
    return terms


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
    reddit_posts, news_items, hn_stories, trend_terms = [], [], [], []

    for sub in ("personalfinance", "financialindependence"):
        try:
            reddit_posts.extend(fetch_reddit(sub))
        except (URLError, HTTPError, ValueError, KeyError) as e:
            errors.append("reddit r/%s: %s" % (sub, e))

    for query in ("personal finance", "budgeting tips", "saving money"):
        try:
            news_items.extend(fetch_gnews(query, limit=8))
        except (URLError, HTTPError, ET.ParseError, ValueError) as e:
            errors.append("google news '%s': %s" % (query, e))

    try:
        hn_stories = fetch_hn()
    except (URLError, HTTPError, ValueError, KeyError) as e:
        errors.append("hacker news: %s" % e)

    try:
        trend_terms = fetch_gtrends_us()
    except (URLError, HTTPError, ET.ParseError, ValueError) as e:
        errors.append("google trends us: %s" % e)

    # Dedupe across sources by normalized title/term, keeping first occurrence.
    seen = set()

    def fresh(key):
        n = norm_title(key)
        if not n or n in seen:
            return False
        seen.add(n)
        return True

    news_items = [n for n in news_items if fresh(n["title"])]
    hn_stories = [s for s in hn_stories if fresh(s["title"])]
    trend_terms = [t for t in trend_terms if fresh(t["term"])]

    if not (reddit_posts or news_items or hn_stories or trend_terms):
        msg = "All trend sources failed: %s" % "; ".join(errors)
        if TRENDS_FILE.exists():
            print(msg + " -- keeping previous trends file.", file=sys.stderr)
            return 0
        print(msg, file=sys.stderr)
        return 1

    titles = (
        [p["title"] for p in reddit_posts]
        + [n["title"] for n in news_items]
        + [s["title"] for s in hn_stories]
        + [t["term"] for t in trend_terms]
    )

    questions = []
    for p in reddit_posts:
        t = p["title"].strip()
        if t.endswith("?") or QUESTION_STARTS.match(t):
            questions.append(p)
    questions.sort(key=lambda p: p["comments"], reverse=True)

    pool = [
        {**p, "kind": "reddit"} for p in reddit_posts
    ] + [
        {**s, "kind": "hn"} for s in hn_stories
    ]
    highlights = sorted(pool, key=lambda p: p.get("score", 0), reverse=True)[:10]

    payload = {
        "fetched_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "sources": [
            "Reddit r/personalfinance + r/financialindependence (public JSON)",
            "Google News RSS (personal finance searches)",
            "Hacker News top stories, finance-filtered (public Firebase API)",
            "Google Trends US daily trending searches, finance-filtered (RSS)",
        ],
        "topics": top_keywords(titles),
        "questions": questions[:12],
        "discussion_highlights": [
            {
                "title": p["title"],
                "source": p["source"],
                "url": p["url"],
                "score": p.get("score", 0),
                "comments": p.get("comments", 0),
            }
            for p in highlights
        ],
        "news": news_items[:15],
        "hn_stories": hn_stories[:10],
        "trending_searches": trend_terms[:12],
        "errors": errors,
    }
    DATA_DIR.mkdir(exist_ok=True)
    TRENDS_FILE.write_text(
        json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )
    print(
        "Wrote %s: %d reddit, %d news, %d hn, %d trends, %d errors."
        % (
            TRENDS_FILE,
            len(reddit_posts),
            len(news_items),
            len(hn_stories),
            len(trend_terms),
            len(errors),
        )
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
