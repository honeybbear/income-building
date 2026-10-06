# Income Building

An autonomous niche publishing operation for **personal finance & budgeting** — a visual "building" where each floor is a department of agents working one pipeline: find what people really ask about, create honest guides and tools, publish daily, and monetize transparently.

Live page: served via GitHub Pages from the repo root (`index.html`).

## The four floors

| Floor | Department | Agents | Job |
|-------|-----------|--------|-----|
| 4 | Monetization | Affiliate Manager, Product Scout | Revenue slots and product ideas — placeholders stay empty until real accounts are connected |
| 3 | Publishing | Editor, Publisher | Accuracy gate and daily shipping to the site |
| 2 | Creation | Guide Writer, Tool Builder | Evergreen guides and the on-site 50/30/20 budget splitter |
| 1 | Scouting | Trend Scout, Question Miner | Daily topic and question discovery from public sources |

Tap any floor or agent on the page to see its current task, what it receives from the floor below, what it sends upward, and its reasoning. Information packets animate between floors (pause / speed controls included).

## How it runs itself

- **`scout.py`** (daily, 06:00 UTC via GitHub Actions): pulls free public sources — Google News RSS for personal finance topics and Reddit's public JSON for r/personalfinance / r/financialindependence (Reddit frequently blocks datacenter IPs, so the script degrades gracefully and records the error). Writes `data/trends.json` with real topics, real quoted questions, and news highlights. Never invents data.
- **`build.py`**: converts `articles/*.md` into `data/articles.json` (stdlib only).
- **`.github/workflows/daily.yml`**: runs both scripts on a cron schedule plus manual trigger, commits changed `data/*.json` back.
- **The site** (`index.html` + `app.js`) renders everything from `data/`: articles, trends, and affiliate slots. If data files are missing it says so honestly instead of faking content.

## Data sources

- Google News RSS (free, no key): `news.google.com/rss/search`
- Reddit public JSON (free, no key; often 403s from servers — handled)
- ESPN-style approach is not used here; all finance content is written by a human author in `articles/`

## Honest notes

- **Traffic and revenue take time.** The machine runs daily from day one; dollars follow months of compounding readership, not the first week. Anyone promising otherwise is selling something.
- **Owner's next steps to earn:** sign up for affiliate programs (budgeting apps, brokerages, banks) and paste the URLs into `data/affiliates.json`; optionally point a custom domain at the Pages site.
- **Content is educational, not financial advice.** Every guide says so, with "last reviewed" dates. No fake statistics — only widely-established facts or clearly-labeled general guidance.
- **Affiliate disclosure** is in the site footer and activates on any real link (`rel="sponsored"`).
- This site publishes information and tools. It never places wagers, trades, or moves money.

## Local preview

```bash
python3 build.py && python3 scout.py
python3 -m http.server 8000
# open http://localhost:8000
```

(`file://` won't work — `fetch()` needs http.)
