#!/usr/bin/env python3
"""Turn the top scout briefs into article drafts (stdlib only).

Two modes:
  - With GEMINI_API_KEY set (Google AI Studio, free tier): the top 3 scout
    briefs are expanded into full article drafts via the Gemini REST API.
    Drafts are strictly grounded in the scouted material — the prompt forbids
    invented statistics, quotes, or facts — and each draft is labeled
    "AI draft, needs human review". Written to data/drafts.json.
  - Without a key: structured briefs (headline options, outline, key points
    pulled from real sources) are written to data/briefs.json. The site shows
    these as "draft briefs awaiting the Creator". Nothing is fabricated.

On any failure the error is recorded; existing data files are left intact.
"""
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

ROOT = Path(__file__).resolve().parent
DATA_DIR = ROOT / "data"
TRENDS_FILE = DATA_DIR / "trends.json"
BRIEFS_FILE = DATA_DIR / "briefs.json"
DRAFTS_FILE = DATA_DIR / "drafts.json"

GEMINI_MODEL = "gemini-2.0-flash"
GEMINI_URL = (
    "https://generativelanguage.googleapis.com/v1beta/models/%s:generateContent"
    % GEMINI_MODEL
)


def utcnow():
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def build_briefs(trends):
    """Assemble up to 3 briefs from real scouted material."""
    briefs = []

    # Prefer real reader questions — they are ready-made article prompts.
    for q in (trends.get("questions") or [])[:2]:
        briefs.append(
            {
                "id": "q-%d" % len(briefs),
                "kind": "reader-question",
                "headline_options": [
                    q["title"].rstrip("?") + "?",
                    "What to know before you ask: " + q["title"].lower().rstrip("?"),
                    q["title"].rstrip("?") + ", answered honestly",
                ],
                "angle": "Answer a real question people are asking, with practical steps.",
                "outline": [
                    "The question, in plain English",
                    "Why it comes up (context)",
                    "What actually works — practical steps",
                    "Common mistakes to avoid",
                    "When to get professional advice",
                ],
                "key_points": [
                    "Real discussion: %s (%s, %d comments)"
                    % (q["title"], q["source"], q.get("comments", 0))
                ],
                "sources": [
                    {"title": q["title"], "url": q["url"], "source": q["source"]}
                ],
            }
        )
        if len(briefs) >= 3:
            return briefs

    # Then top scouted topics, grounded in the items that mention them.
    topics = trends.get("topics") or []
    searchable = (
        [(n.get("title", ""), n.get("link", ""), n.get("source", "")) for n in trends.get("news", [])]
        + [(s.get("title", ""), s.get("url", ""), s.get("source", "")) for s in trends.get("hn_stories", [])]
    )
    for t in topics:
        kw = t["keyword"]
        hits = [
            {"title": ti, "url": u, "source": s}
            for ti, u, s in searchable
            if kw in ti.lower()
        ][:4]
        if not hits:
            continue
        cap = kw.capitalize()
        briefs.append(
            {
                "id": "t-%d" % len(briefs),
                "kind": "trending-topic",
                "headline_options": [
                    "%s, explained in plain English" % cap,
                    "What you should actually know about %s" % kw,
                    "%s: the honest beginner's guide" % cap,
                ],
                "angle": "Evergreen explainer on a topic people are actively reading about.",
                "outline": [
                    "What %s means in plain English" % kw,
                    "Why it matters for your budget",
                    "What the current discussion is saying",
                    "Common mistakes",
                    "Sensible next steps",
                ],
                "key_points": ["%s (%s)" % (h["title"], h["source"]) for h in hits],
                "sources": hits,
            }
        )
        if len(briefs) >= 3:
            break
    return briefs


DRAFT_SYSTEM = (
    "You are drafting a practical personal-finance guide for a general US audience. "
    "Use ONLY the material provided below. Do not invent statistics, quotes, studies, "
    "prices, or facts that are not in the material. If the material is thin, write a "
    "shorter piece and end with a 'Still to research' list of what a human should verify. "
    "Plain, honest tone. No hype, no promises of returns. End with a 'Sources' list using "
    "only the provided links."
)


def gemini_draft(api_key, brief):
    material = "\n".join(
        "- [%s] %s (%s)" % (s.get("source", ""), s.get("title", ""), s.get("url", ""))
        for s in brief["sources"]
    )
    prompt = (
        DRAFT_SYSTEM
        + "\n\nWorking headline: %s\nAngle: %s\nOutline:\n%s\n\nSource material:\n%s"
        % (
            brief["headline_options"][0],
            brief["angle"],
            "\n".join("* " + o for o in brief["outline"]),
            material,
        )
    )
    body = json.dumps(
        {
            "contents": [{"parts": [{"text": prompt}]}],
            "generationConfig": {"temperature": 0.7, "maxOutputTokens": 2048},
        }
    ).encode("utf-8")
    req = Request(
        GEMINI_URL,
        data=body,
        headers={"Content-Type": "application/json", "x-goog-api-key": api_key},
    )
    with urlopen(req, timeout=90) as resp:
        data = json.loads(resp.read().decode("utf-8", errors="replace"))
    return data["candidates"][0]["content"]["parts"][0]["text"]


def main():
    if not TRENDS_FILE.exists():
        print("No data/trends.json — run scout.py first.", file=sys.stderr)
        return 1
    trends = json.loads(TRENDS_FILE.read_text(encoding="utf-8"))
    briefs = build_briefs(trends)
    if not briefs:
        print("No brief material in trends file — nothing to draft.", file=sys.stderr)
        return 0

    api_key = os.environ.get("GEMINI_API_KEY", "").strip()
    if not api_key:
        payload = {
            "generated_at": utcnow(),
            "mode": "briefs-only",
            "note": "No GEMINI_API_KEY set. These are structured briefs awaiting the Creator — "
            "not finished articles. See README for the 2-minute key setup.",
            "briefs": briefs,
        }
        BRIEFS_FILE.write_text(
            json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
        )
        print("Wrote %s: %d briefs (no API key; drafts skipped honestly)." % (BRIEFS_FILE, len(briefs)))
        return 0

    drafts, errors = [], []
    for b in briefs:
        try:
            text = gemini_draft(api_key, b)
            drafts.append(
                {
                    "brief_id": b["id"],
                    "title": b["headline_options"][0],
                    "body": text,
                    "sources": b["sources"],
                    "note": "AI draft via %s — requires human review before publishing." % GEMINI_MODEL,
                }
            )
        except (URLError, HTTPError, ValueError, KeyError) as e:
            errors.append("draft %s: %s" % (b["id"], e))
    payload = {
        "generated_at": utcnow(),
        "mode": "ai-drafts",
        "model": GEMINI_MODEL,
        "drafts": drafts,
        "errors": errors,
    }
    DRAFTS_FILE.write_text(
        json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )
    print("Wrote %s: %d drafts, %d errors." % (DRAFTS_FILE, len(drafts), len(errors)))
    return 0


if __name__ == "__main__":
    sys.exit(main())
