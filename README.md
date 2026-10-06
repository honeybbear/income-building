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

- **`scout.py`** (daily, 06:00 UTC via GitHub Actions): pulls free public sources — Google News RSS for personal finance topics, Hacker News top stories (finance-keyword filtered, word-boundary matched), Google Trends US daily trending searches (finance-filtered), and Reddit's public JSON for r/personalfinance / r/financialindependence (Reddit frequently blocks datacenter IPs, so the script degrades gracefully and records the error). Topics are deduped across sources with per-source attribution. Writes `data/trends.json` with real topics, real quoted questions, HN discussions, trending searches, and news highlights. Never invents data.
- **`draft.py`**: turns the top 3 scout briefs into structured briefs (`data/briefs.json`) — headline options, outline, key points pulled from real sources. If a `GEMINI_API_KEY` repo secret is set, it instead drafts full articles grounded strictly in the scouted material (`data/drafts.json`), each labeled "AI draft — needs human review". Without the key it honestly no-ops to briefs.
- **`build.py`**: converts `articles/*.md` into `data/articles.json` (stdlib only).
- **`.github/workflows/daily.yml`**: runs all three scripts on a cron schedule plus manual trigger, commits changed `data/*.json` back.
- **The site** (`index.html` + `app.js`) renders everything from `data/`: articles, trends, briefs/drafts, products, and affiliate slots. If data files are missing it says so honestly instead of faking content.

## Optional AI drafting (2-minute setup)

1. Go to [Google AI Studio](https://aistudio.google.com/) and sign in (free tier, no card).
2. Click "Get API key" → "Create API key" and copy it.
3. In this repo: Settings → Secrets and variables → Actions → New repository secret. Name: `GEMINI_API_KEY`, value: your key.
4. Done. The next daily run (or a manual "Run workflow") will draft full articles from that day's briefs into `data/drafts.json`, shown on the site as "AI draft — needs human review". Remove the secret any time to go back to briefs-only mode.

## Data sources

- Google News RSS (free, no key): `news.google.com/rss/search`
- Hacker News public Firebase API (free, no key): `hacker-news.firebaseio.com`
- Google Trends US daily RSS (free, no key): `trends.google.com/trending/rss?geo=US`
- Reddit public JSON (free, no key; often 403s from servers — handled)

## Activating affiliate revenue (one-ID setup)

Each slot in `data/affiliates.json` has an `id_template` (the credential name, e.g. `amazon_tag`), a `tag` (your affiliate ID), a `mention` (the product name the site auto-links inside articles), and a `url`. To activate:

1. **Amazon Associates**: sign up at affiliate-program.amazon.com → get your tracking ID (looks like `yoursite-20`). Set the slot's `tag` to it, `mention` to the product name as written in the article (e.g. `"YNAB"`), and `url` to the product search URL with your tag, e.g. `https://www.amazon.com/s?k=ynab&tag=yoursite-20`.
2. **Any program with a plain link** (bank, brokerage, SaaS): paste the full referral URL into `url` and set `tag` to any non-empty label (e.g. `"chase-referral"`). `mention` is optional.
3. Commit the change. The site auto-links the product mention inside articles with `rel="sponsored"` and the slot card becomes a labeled affiliate link. Slots left with `url: null` keep rendering the honest "coming soon" state — and earn nothing.

## Digital products

`products/budget-planner/` holds the first product: a free, printable monthly budget planner (live totals in the browser, print CSS, CSV template). It's listed on the site under Products as a real free download. To sell a premium version: create a product on Gumroad or a Stripe Payment Link, then set the product's `payment_url` (and `price`) in `data/products.json`. Until then the site shows "connect a payment link to sell" — prices and checkouts are never faked.

## Honest notes

- **Traffic and revenue take time.** The machine runs daily from day one; dollars follow months of compounding readership, not the first week. Anyone promising otherwise is selling something.
- **Owner's next steps to earn:** sign up for affiliate programs and set each slot's `tag`/`url` in `data/affiliates.json` (see "Activating affiliate revenue" above); add a Gumroad/Stripe payment link to `data/products.json` to sell the budget planner premium version; optionally point a custom domain at the Pages site.
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
