# C2FO Strategy Tracker

A Python script that scrapes [C2FO](https://c2fo.com)'s public newsroom and blog,
classifies each article into one of seven strategic themes, and produces a CSV plus
two charts. Built as a portfolio piece for a marketing analyst role at SAP Taulia
(C2FO is one of Taulia's main competitors in supply chain finance).

## What it does

1. **Scrapes** `https://c2fo.com/newsroom/` and `https://c2fo.com/blog/` using
   `requests` + `BeautifulSoup`. The site is server-rendered WordPress, so no
   JavaScript fallback is needed.
2. **Walks pagination** automatically (capped at 15 pages as a safety net).
3. **Enriches** each article by visiting its individual page and reading the
   `<meta name="description">` and `<meta property="article:published_time">` tags.
4. **Classifies** each article into one of seven strategic themes
   (ESG / Sustainability, Awards / Recognition, Thought Leadership,
   Geographic Expansion, Partnership, Product Launch, Other) using a keyword
   dictionary with word-boundary matching.
5. **Outputs** a CSV, a theme bar chart, a monthly timeline chart, and a printed
   strategic summary.

## How to run

```bash
cd ~/Desktop/c2fo-strategy-tracker
python3 c2fo_tracker.py
```

The first run automatically installs `requests`, `beautifulsoup4`, `pandas`,
and `matplotlib` via `pip install --user`. Subsequent runs skip installation
and finish in roughly 30 seconds (most of the time is the polite delay between
requests to C2FO's server).

No virtual environment is required — packages go into your user site folder
(`~/Library/Python/3.9/lib/python/site-packages/`) and don't touch system Python.

## Output files

| File | Contents |
| --- | --- |
| `c2fo_strategy_data.csv` | Full dataset: source (newsroom/blog), title, date, URL, description, strategic theme. One row per article. |
| `c2fo_strategy_chart.png` | Horizontal bar chart of articles per strategic theme (the headline visual). |
| `c2fo_timeline_chart.png` | Vertical bar chart of articles per calendar month (publishing cadence). |

## Tweaking the classifier

The keyword dictionary lives in `THEME_KEYWORDS` near the top of
`c2fo_tracker.py`. Each theme is a list of lowercase keywords. **Order
matters** — themes higher in the dictionary win ties. To change how an
article is classified, add or remove keywords for the relevant theme,
or move a theme up/down in the dictionary.

Matching uses word boundaries (`\b`), so `"esg"` matches the word `esg`
but **not** the substring inside `riesgo` (Spanish for "risk"). This was a
real bug in an earlier version — keep word boundaries on if you add new
short keywords.

## Re-running with a clean slate

If you want a fresh run, just delete the three output files and re-run:

```bash
rm c2fo_strategy_data.csv c2fo_strategy_chart.png c2fo_timeline_chart.png
python3 c2fo_tracker.py
```

## What this is meant to demonstrate

For an interview at SAP Taulia, this script demonstrates:

- **Competitive intelligence** — turning a competitor's public PR + content into
  a structured dataset rather than a vibe.
- **Practical web scraping** — including the right defensive moves: a real
  User-Agent, polite delays, pagination, fallback meta-tag enrichment, absolute
  URL resolution.
- **Categorisation logic** — explicit, editable, transparent (no black box).
- **Strategic interpretation** — the printed summary names the dominant theme
  and gives a one-sentence read on what it implies for C2FO's positioning.
