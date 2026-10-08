#!/usr/bin/env python3
"""Convert articles/*.md into data/articles.json using only the stdlib.

Article format:
    # Title
    > Excerpt line(s)
    Reviewed: Month D, YYYY
    <blank>
    Body with ## headings, - lists, **bold**, *italic*.
"""
import html
import json
import re
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent
ARTICLES_DIR = ROOT / "articles"
DATA_DIR = ROOT / "data"

TOPICS = {
    "budgeting-basics": ["budgeting", "getting started"],
    "emergency-fund": ["saving", "getting started"],
    "kill-high-interest-debt": ["debt", "getting started"],
    "beginner-investing-index-funds": ["investing"],
    "cut-subscriptions-bills": ["saving", "budgeting"],
    "second-income-stream": ["income", "getting started"],
    "mortgage-rates-rising-playbook": ["debt", "budgeting"],
    "trump-account-vs-529": ["investing", "family"],
}


def inline_md(text):
    """Escape HTML, then convert **bold** and *italic*."""
    text = html.escape(text)
    text = re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", text)
    text = re.sub(r"\*(.+?)\*", r"<em>\1</em>", text)
    return text


def md_to_html(body):
    """Very small markdown subset -> HTML. Blocks separated by blank lines."""
    blocks = re.split(r"\n\s*\n", body.strip())
    out = []
    i = 0
    while i < len(blocks):
        block = blocks[i].strip()
        lines = block.split("\n")
        if block.startswith("### "):
            out.append("<h3>%s</h3>" % inline_md(block[4:].strip()))
        elif block.startswith("## "):
            out.append("<h2>%s</h2>" % inline_md(block[3:].strip()))
        elif all(l.strip().startswith("- ") for l in lines):
            items = "".join("<li>%s</li>" % inline_md(l.strip()[2:]) for l in lines)
            out.append("<ul>%s</ul>" % items)
        else:
            out.append("<p>%s</p>" % inline_md(" ".join(l.strip() for l in lines)))
        i += 1
    return "\n".join(out)


def parse_article(path):
    text = path.read_text(encoding="utf-8")
    lines = text.split("\n")
    title, excerpt_lines, reviewed = "", [], ""
    body_start = 0
    for idx, line in enumerate(lines):
        s = line.strip()
        if s.startswith("# ") and not title:
            title = s[2:].strip()
        elif s.startswith("> "):
            excerpt_lines.append(s[2:].strip())
        elif s.lower().startswith("reviewed:"):
            reviewed = s.split(":", 1)[1].strip()
        elif s == "" and title and excerpt_lines and reviewed:
            body_start = idx + 1
            break
    body = "\n".join(lines[body_start:])
    words = len(re.findall(r"[A-Za-z']+", body))
    return {
        "slug": path.stem,
        "title": title,
        "excerpt": " ".join(excerpt_lines),
        "reviewed": reviewed,
        "topics": TOPICS.get(path.stem, []),
        "words": words,
        "html": md_to_html(body),
    }


def main():
    DATA_DIR.mkdir(exist_ok=True)
    articles = []
    for path in sorted(ARTICLES_DIR.glob("*.md")):
        art = parse_article(path)
        if not art["title"]:
            raise SystemExit("Could not parse title in %s" % path.name)
        articles.append(art)
    payload = {
        "generated_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "count": len(articles),
        "articles": articles,
    }
    out = DATA_DIR / "articles.json"
    out.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print("Wrote %s with %d articles." % (out, len(articles)))


if __name__ == "__main__":
    main()
