#!/usr/bin/env python3
# The line above tells the operating system to run this file with Python 3.

# ---------------------------------------------------------------------------
# c2fo_tracker.py
# A beginner-friendly script that scrapes C2FO's public newsroom + blog,
# classifies each article into a strategic theme, and produces a CSV and
# two charts that you can use in a portfolio for a marketing analyst role.
# ---------------------------------------------------------------------------

# We need a few extra Python libraries that are not built in. The block below
# tries to import them, and if any are missing, it installs them automatically
# using "pip" (Python's package installer) and then imports them again.

import sys           # "sys" gives us access to the running Python interpreter (we need its path to run pip with the SAME Python).
import site          # "site" knows where Python looks for installed packages, including the per-user folder.
import importlib     # "importlib" lets us refresh Python's knowledge of what packages exist after a fresh install.
import subprocess    # "subprocess" lets Python run other command-line programs (we use it to call pip).
import warnings      # "warnings" lets us hide a harmless macOS LibreSSL warning that would otherwise clutter the output.
warnings.filterwarnings("ignore")                       # Silence non-fatal warnings so the terminal output stays clean.

# A small helper function that makes sure a library is installed before we use it.
def ensure_installed(package_name, import_name=None):
    # "package_name" is what pip calls the library; "import_name" is what Python's import statement calls it.
    import_name = import_name or package_name           # If we didn't pass an import name, reuse the package name.
    try:                                                # Try the optimistic path first.
        __import__(import_name)                         # __import__ is the lower-level form of "import"; it accepts a string.
        return                                          # Already installed — nothing more to do.
    except ImportError:                                 # If Python can't find the library, we install it.
        print(f"Installing missing library: {package_name} ...")  # Tell the user what is happening.

    subprocess.check_call(                              # check_call runs the command and raises an error if it fails.
        [sys.executable, "-m", "pip", "install", "--user", "--quiet", package_name]
        # "sys.executable" = path to the current Python; "-m pip" runs the pip module;
        # "--user" installs into the user's home folder so we don't need admin rights;
        # "--quiet" hides pip's noisy output so the terminal stays readable.
    )

    # After a fresh install we have to teach the running Python about the new package:
    user_site = site.getusersitepackages()              # The folder pip --user just installed into.
    if user_site not in sys.path:                       # If that folder is not yet on Python's import search path...
        sys.path.insert(0, user_site)                   # ...add it to the front so the new package can be found.
    importlib.invalidate_caches()                       # Tell Python to forget its earlier "module not found" lookups.
    __import__(import_name)                             # Try the import one more time, now that it's installed and visible.

# Make sure all four third-party libraries are available before we go further.
ensure_installed("requests")                            # "requests" downloads web pages.
ensure_installed("beautifulsoup4", "bs4")               # "beautifulsoup4" parses HTML; its import name is "bs4".
ensure_installed("pandas")                              # "pandas" is a spreadsheet-like data table for Python.
ensure_installed("matplotlib")                          # "matplotlib" draws charts.

# Now that we know the libraries exist, we can import them for real.
import re                                               # "re" is for regular expressions (text pattern matching).
import time                                             # "time" lets us pause between web requests so we are polite to the server.
from datetime import datetime                           # "datetime" lets us work with dates.
from urllib.parse import urljoin                        # "urljoin" turns a relative URL like "/foo/" into a full one like "https://c2fo.com/foo/".

import requests                                         # The actual HTTP-downloading library.
from bs4 import BeautifulSoup                           # The HTML-parsing library.
import pandas as pd                                     # We rename pandas to "pd" because that is the universal convention.
import matplotlib                                       # Import matplotlib so we can configure it before use.
matplotlib.use("Agg")                                   # "Agg" is a backend that draws to image files without needing a screen window.
import matplotlib.pyplot as plt                         # "pyplot" is matplotlib's main plotting interface; "plt" is the conventional nickname.

# ---------------------------------------------------------------------------
# CONFIGURATION
# These constants control where we scrape from, how aggressively, and how
# we classify articles. Edit values here without touching the logic below.
# ---------------------------------------------------------------------------

NEWSROOM_URL = "https://c2fo.com/newsroom/"             # Starting URL for the press-release / news section.
BLOG_URL = "https://c2fo.com/blog/"                     # Starting URL for the blog / thought-leadership section.

# We pretend to be a normal Mac browser so the website does not block us as a bot.
HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "    # Says we are a Mac.
        "AppleWebKit/537.36 (KHTML, like Gecko) "             # Says we use a WebKit-style browser engine.
        "Chrome/120.0.0.0 Safari/537.36"                       # Says we are Chrome version 120.
    )
}

MAX_LISTING_PAGES = 15                                  # Stop walking pagination after this many pages, just in case.
REQUEST_DELAY_SECONDS = 0.6                             # Pause between requests so we don't hammer C2FO's server.
REQUEST_TIMEOUT_SECONDS = 20                            # If a single request takes longer than this, give up and move on.

# The seven strategic themes the user wants. Each theme maps to a list of
# keywords (lower-case). We match keywords using *word boundaries*, so
# "esg" will match the word "esg" but NOT the substring inside "riesgo".
#
# Order matters — themes higher in the dictionary win ties:
#   1. ESG comes first because sustainability messaging is a deliberate angle
#      that should override more generic signals.
#   2. Awards / Recognition: explicit award + milestone language is unambiguous.
#   3. Thought Leadership BEFORE Geographic, so a "Delayed Payments Report"
#      that mentions India lands as research, not as expansion.
#   4. Geographic Expansion picks up clear country/market mentions next.
#   5. Partnership and Product Launch are last because their keywords
#      (e.g. "launches", "partners with") often appear inside other categories.
THEME_KEYWORDS = {
    "ESG / Sustainability": [
        "esg", "sustainable", "sustainability", "green finance", "green",
        "climate", "carbon", "net zero", "net-zero", "decarbonization",
        "renewable", "social impact", "diversity", "inclusion", "scope 3",
        "transition finance", "inclusive growth",
    ],
    "Awards / Recognition": [
        "award", "awards", "honored", "honoured", "recognized", "recognised",
        "wins", "winner", "ranking", "ranked", "top fintech", "best",
        "named", "fortune", "milestone", "prestigious",
    ],
    "Thought Leadership": [
        "report", "whitepaper", "white paper", "survey", "research", "outlook",
        "trend", "trends", "study", "index", "guide", "guía", "playbook",
        "perspective", "insight", "insights", "commentary", "analysis",
        "what is", "why", "how to", "qué es", "por qué", "cómo",
        "case study", "caso de estudio", "customer story",
    ],
    "Geographic Expansion": [
        "expand", "expands", "expansion", "new market", "enters", "launches in",
        "launch in", "india", "africa", "nigeria", "europe", "germany", "uk",
        "u.k.", "asia", "latin america", "mexico", "brazil", "spain", "japan",
        "china", "regional", "global", "globe", "international", "emerging markets",
        "msme", "msmes",
    ],
    "Partnership": [
        "partner", "partners", "partnership", "alliance", "collaboration",
        "collaborates", "joins forces", "integration", "integrates", "ifc",
        "powered by", "team up", "teams up", "with citi", "with hsbc",
        "with wells", "with pwc",
    ],
    "Product Launch": [
        "launch", "launches", "launched", "introduces", "unveils", "rolls out",
        "new feature", "new platform", "new product", "release", "upgraded",
        "platform update", "new tool", "raises",
    ],
}

# ---------------------------------------------------------------------------
# HELPER FUNCTIONS
# ---------------------------------------------------------------------------

def fetch_html(url):
    # Download a single web page and return its raw HTML text, or None if it failed.
    try:                                                                # We wrap the network call in try/except so one bad page doesn't crash the script.
        response = requests.get(url, headers=HEADERS,                    # Send a GET request with our pretend-browser headers.
                                timeout=REQUEST_TIMEOUT_SECONDS)         # Don't wait forever if the server is slow.
        response.raise_for_status()                                      # Raise an exception if the server returned an error code (404, 500, etc.).
        time.sleep(REQUEST_DELAY_SECONDS)                                # Be polite — small pause before the next request.
        return response.text                                             # Return the page's HTML as a string.
    except requests.RequestException as exc:                             # Catch any network-related error.
        print(f"  ! Could not fetch {url} ({exc})")                       # Tell the user which URL failed and why.
        return None                                                       # Return None so callers can skip this page gracefully.


def parse_date_string(raw_date):
    # Convert a human-readable date like "November 12, 2025" into a real date object.
    if not raw_date:                                                     # If the input is empty or None, give up early.
        return None                                                       # Return None to signal "no date".
    raw_date = raw_date.strip()                                          # Remove leading/trailing whitespace.
    # Try several formats because dates appear in different shapes on the site.
    formats_to_try = [
        "%B %d, %Y",        # e.g. "November 12, 2025"
        "%b %d, %Y",        # e.g. "Nov 12, 2025"
        "%Y-%m-%d",         # e.g. "2025-11-12"
        "%Y-%m-%dT%H:%M:%S",  # ISO format from <meta> tags, no timezone
        "%Y-%m-%dT%H:%M:%S%z",  # ISO format with a timezone offset
    ]
    for fmt in formats_to_try:                                           # Try each format until one works.
        try:
            return datetime.strptime(raw_date[:25], fmt)                  # strptime parses a string into a datetime; we trim long ISO strings.
        except ValueError:                                                # If this format didn't match, try the next one.
            continue
    return None                                                           # If nothing matched, give up and return None.


def extract_listing_articles(html, source_label):
    # Pull out the article cards from one listing page (newsroom or blog) and
    # return a list of dictionaries, each describing one article.
    soup = BeautifulSoup(html, "html.parser")                            # Parse the HTML into a navigable tree.
    articles = []                                                        # We'll collect article dicts in this list.
    seen_urls = set()                                                    # Track URLs we've already added so we don't duplicate.

    # Articles are linked from the listing in two patterns we care about:
    #   /newsroom/<slug>/   (press releases, news pieces)
    #   /resources/<category>/<slug>/   (blog / thought-leadership pieces)
    link_selector = "a[href*='/newsroom/'], a[href*='/resources/']"      # CSS selector matching either link pattern.

    # We use a regex to detect generic call-to-action link text like "Read More",
    # "Read more >", "Learn more", etc. — these aren't real article titles.
    cta_pattern = re.compile(r"^(read|learn|view|see)\s+more.*", re.IGNORECASE)

    for link in soup.select(link_selector):                              # Loop over every matching <a> tag in the page.
        raw_url = link.get("href", "").strip()                            # Read the link's URL (the "href" attribute).
        if not raw_url:                                                   # Skip empty links.
            continue
        # Convert relative URLs (starting with "/") into absolute ones (starting with "https://c2fo.com/...").
        url = urljoin("https://c2fo.com/", raw_url)
        # Filter out junk links: pagination, the listing pages themselves, anchors, etc.
        if "/newsroom/page/" in url or "/blog/page/" in url:             # Pagination links — skip.
            continue
        if url.rstrip("/").endswith("/newsroom") or url.rstrip("/").endswith("/blog"):  # The landing page itself.
            continue
        if url in seen_urls:                                              # Already saw this URL on this page.
            continue

        # We only want links that look like real article URLs (have a slug after the section).
        if not re.search(r"/(newsroom|resources)/[^/]+/[^/]*", url) and not re.search(r"/newsroom/[^/]+/", url):
            continue

        # Find a title for this link. The title is usually the link's own text,
        # OR the text of an <h2>/<h3> element that the link sits inside or contains.
        title_text = link.get_text(strip=True)                            # Try the link's visible text first.
        # If the link is just a generic "Read More" button, look for the real title nearby.
        if not title_text or len(title_text) < 5 or cta_pattern.match(title_text):
            heading = link.find_parent(["h1", "h2", "h3", "h4"])          # First, check if the link sits inside a heading.
            if heading:
                title_text = heading.get_text(strip=True)
            else:
                # Climb to the wrapping card and look for a heading sibling there.
                card = link.find_parent(["div", "article", "li"])
                if card:
                    nearby_heading = card.find(["h1", "h2", "h3", "h4"])
                    if nearby_heading:
                        title_text = nearby_heading.get_text(strip=True)
        if not title_text or len(title_text) < 5:                         # Still no usable title? Skip this link.
            continue
        if cta_pattern.match(title_text):                                 # If it's still just a CTA button, skip it.
            continue

        # Try to find a date for this card. On the newsroom page, dates appear
        # as plain text right next to the categories ("| November 12, 2025").
        # We look at the card's outer container for any text that looks like a date.
        card = link.find_parent(["div", "article", "li"])                 # Climb up to the wrapping element.
        date_text = None                                                  # Default: no date found.
        if card:
            card_text = card.get_text(" ", strip=True)                    # Flatten the card's text into one string.
            # Regex: match Month-name DD, YYYY patterns like "November 12, 2025".
            match = re.search(
                r"\b(January|February|March|April|May|June|July|August|"
                r"September|October|November|December)\s+\d{1,2},\s+\d{4}\b",
                card_text,
            )
            if match:                                                     # If the regex found a date string...
                date_text = match.group(0)                                # ...keep it as a raw string for now.

        articles.append({                                                 # Add this article's data to our list.
            "source": source_label,                                       # "newsroom" or "blog" — useful for filtering later.
            "title": title_text,                                          # The article's headline.
            "url": url,                                                   # Direct link to the full article.
            "date_raw": date_text,                                        # Date as a string (might be None).
            "description": "",                                            # Description starts empty; we fill it in later.
        })
        seen_urls.add(url)                                                # Mark this URL as seen so we don't add it twice.

    return articles                                                      # Hand the list back to the caller.


def find_next_page_url(html):
    # Look for a "next page" pagination link in the listing HTML and return its URL,
    # or None if there is no next page.
    soup = BeautifulSoup(html, "html.parser")                            # Parse the page.
    # WordPress puts the next page either in <link rel="next"> in the <head>...
    rel_next = soup.find("link", attrs={"rel": "next"})                  # Look for the head <link rel="next">.
    if rel_next and rel_next.get("href"):                                # If we found one with a real URL...
        return rel_next["href"]                                          # ...return it.
    # ...or as a normal <a class="next"> link in the page body.
    a_next = soup.find("a", attrs={"class": re.compile("next", re.I)})   # Find an <a> whose class contains "next".
    if a_next and a_next.get("href"):                                    # If found...
        return a_next["href"]                                            # ...return its URL.
    return None                                                          # No next page found.


def scrape_listing(start_url, source_label):
    # Walk through every page of a listing (newsroom or blog) and collect articles.
    print(f"\n--- Scraping {source_label} starting at {start_url} ---")  # Friendly progress message.
    all_articles = []                                                    # Master list of articles for this section.
    current_url = start_url                                              # We begin at the first page.
    pages_visited = 0                                                    # Counter so we don't loop forever.
    seen_urls_global = set()                                             # Track URLs across pages to avoid duplicates.

    while current_url and pages_visited < MAX_LISTING_PAGES:             # Loop until no next page or we hit the safety cap.
        pages_visited += 1                                               # Count this page.
        print(f"  Page {pages_visited}: {current_url}")                  # Show which page we're on.
        html = fetch_html(current_url)                                   # Download the page.
        if html is None:                                                 # If the fetch failed...
            print("  ! Stopping pagination because the page could not be loaded.")
            break                                                        # ...stop trying further pages.

        page_articles = extract_listing_articles(html, source_label)     # Pull out article cards from this page.
        new_count = 0                                                    # Count how many of them are actually new.
        for article in page_articles:                                    # Loop over articles found on this page.
            if article["url"] in seen_urls_global:                       # Already collected from a previous page?
                continue                                                 # Skip duplicates.
            seen_urls_global.add(article["url"])                         # Remember this URL.
            all_articles.append(article)                                 # Add to our master list.
            new_count += 1                                               # Bump the new-article counter.
        print(f"    Found {new_count} new articles on this page.")      # Progress report.

        if new_count == 0:                                               # If we got nothing new, the listing is exhausted.
            break

        next_url = find_next_page_url(html)                              # Look for the next page link.
        if not next_url or next_url == current_url:                      # If there isn't one (or it loops back), stop.
            break
        current_url = next_url                                           # Otherwise, move on to the next page.

    print(f"  Total articles collected from {source_label}: {len(all_articles)}")
    return all_articles                                                  # Return everything we found.


def enrich_with_meta(articles):
    # For each article, visit its individual page once to pull out a meta
    # description (a clean preview sentence) and a published date.
    print(f"\n--- Enriching {len(articles)} articles with meta description + date ---")
    for index, article in enumerate(articles, start=1):                  # Loop with a 1-based counter for readable progress.
        if index % 10 == 0 or index == 1:                                # Print a progress message every 10 articles.
            print(f"  Enriching article {index} of {len(articles)} ...")
        html = fetch_html(article["url"])                                # Download the individual article page.
        if html is None:                                                 # If the fetch failed, leave fields empty and move on.
            continue
        soup = BeautifulSoup(html, "html.parser")                        # Parse the article's HTML.

        # Try the standard <meta name="description"> tag first.
        meta_desc = soup.find("meta", attrs={"name": "description"})    # Look for it.
        if meta_desc and meta_desc.get("content"):                       # If found and has content...
            article["description"] = meta_desc["content"].strip()        # ...store it.
        else:
            # Fall back to <meta property="og:description"> (Open Graph), used by social previews.
            og_desc = soup.find("meta", attrs={"property": "og:description"})
            if og_desc and og_desc.get("content"):
                article["description"] = og_desc["content"].strip()

        # If we still don't have a date from the listing, pull one from the article's meta tags.
        if not article.get("date_raw"):                                  # Only fetch if we don't already have a date.
            published = soup.find("meta", attrs={"property": "article:published_time"})
            if published and published.get("content"):
                article["date_raw"] = published["content"].strip()       # ISO format like "2025-11-12T14:30:00+00:00".


def classify_article(title, description):
    # Decide which strategic theme an article belongs to, based on keywords.
    text = f"{title} {description}".lower()                              # Combine and lowercase so matching is case-insensitive.
    for theme, keywords in THEME_KEYWORDS.items():                       # Themes are checked in dictionary order — earlier ones win.
        for keyword in keywords:                                          # Loop over each keyword for this theme.
            # Use word boundaries (\b) so "esg" matches the word "esg" but
            # NOT the substring inside "riesgo" (Spanish for "risk"). This
            # makes the classifier much more precise.
            pattern = r"\b" + re.escape(keyword) + r"\b"
            if re.search(pattern, text):                                 # Try the regex match.
                return theme                                              # First match wins, then we stop.
    return "Other"                                                       # Nothing matched — bucket it as "Other".


# ---------------------------------------------------------------------------
# MAIN PIPELINE
# This is the part that actually runs when you execute the script.
# ---------------------------------------------------------------------------

def main():
    print("=" * 70)                                                      # Visual separator in the terminal.
    print("C2FO STRATEGY TRACKER")                                       # Banner so the output is easy to read.
    print("=" * 70)

    # PART A — DATA COLLECTION
    newsroom_articles = scrape_listing(NEWSROOM_URL, "newsroom")         # Grab everything from the newsroom.
    blog_articles = scrape_listing(BLOG_URL, "blog")                     # Grab everything from the blog.
    all_articles = newsroom_articles + blog_articles                     # Combine both into one big list.

    if not all_articles:                                                 # Defensive check — if nothing was collected, bail out clearly.
        print("\nERROR: No articles were collected. The website may have blocked the script,")
        print("or the page layout may have changed. What to try next:")
        print("  1. Check that you can open https://c2fo.com/newsroom/ in your browser.")
        print("  2. Try running the script again in a few minutes (could be a temporary block).")
        print("  3. If it still fails, the page structure has likely changed and the CSS")
        print("     selectors near the top of this file need to be updated.")
        return                                                           # Stop the program here.

    enrich_with_meta(all_articles)                                       # Visit each article to fill in description + date.

    # Move the data into a pandas DataFrame — this is a spreadsheet-like table.
    df = pd.DataFrame(all_articles)                                      # Create the table from our list of dicts.
    df["date"] = df["date_raw"].apply(parse_date_string)                 # Convert the raw date strings into real datetime objects.

    # PART B — CATEGORISATION
    df["strategic_theme"] = df.apply(                                    # Apply our classifier to every row.
        lambda row: classify_article(row["title"], row["description"]),  # For each row, run classify_article on the title + description.
        axis=1,                                                          # axis=1 means "give me each row", not each column.
    )

    # Count how many articles fell into each theme.
    theme_counts = df["strategic_theme"].value_counts()                  # Built-in pandas tally.
    print("\n--- Articles per strategic theme ---")
    print(theme_counts.to_string())                                       # Print the tally as a clean table.

    # If we have dates, also count articles per month.
    dated_df = df.dropna(subset=["date"]).copy()                         # Keep only rows that successfully parsed a date.
    monthly_counts = None                                                # Default: no timeline data.
    if not dated_df.empty:                                               # Only do this if at least one article has a date.
        dated_df["month"] = dated_df["date"].dt.to_period("M")           # "to_period('M')" buckets each date into its calendar month.
        monthly_counts = dated_df.groupby("month").size().sort_index()   # Count articles per month, in chronological order.
        print("\n--- Articles per month ---")
        print(monthly_counts.to_string())
    else:
        print("\nNo dates were parsed, so the monthly timeline will be skipped.")

    # PART C — OUTPUT
    csv_path = "c2fo_strategy_data.csv"                                  # Filename for the CSV.
    # Choose a tidy column order before writing.
    output_columns = ["source", "title", "date", "url", "description", "strategic_theme"]
    df[output_columns].to_csv(csv_path, index=False)                     # Save the DataFrame; index=False omits row numbers.
    print(f"\nSaved dataset to {csv_path}  ({len(df)} rows)")            # Confirm to the user.

    # --- Chart 1: bar chart of themes ---
    chart1_path = "c2fo_strategy_chart.png"                              # Filename for the themes chart.
    plt.figure(figsize=(10, 6))                                          # Create a new figure that is 10x6 inches.
    theme_counts.sort_values().plot(kind="barh", color="#1f6feb")        # Horizontal bar chart, sorted ascending so largest is on top.
    plt.title("C2FO public articles by strategic theme")                 # Chart title.
    plt.xlabel("Number of articles")                                     # X-axis label.
    plt.ylabel("Strategic theme")                                        # Y-axis label.
    plt.tight_layout()                                                   # Auto-adjust margins so labels don't get cut off.
    plt.savefig(chart1_path, dpi=150)                                    # Save as PNG at 150 dpi (fairly crisp).
    plt.close()                                                          # Close the figure to free memory.
    print(f"Saved theme chart to {chart1_path}")

    # --- Chart 2: monthly timeline ---
    chart2_path = "c2fo_timeline_chart.png"                              # Filename for the timeline chart.
    if monthly_counts is not None and len(monthly_counts) > 0:           # Only draw the timeline if we have date data.
        plt.figure(figsize=(11, 5))                                      # Slightly wider chart for the timeline.
        monthly_counts.plot(kind="bar", color="#2da44e")                  # Vertical bar chart of articles per month.
        plt.title("C2FO public articles over time (per month)")          # Chart title.
        plt.xlabel("Month")                                              # X-axis label.
        plt.ylabel("Number of articles")                                 # Y-axis label.
        plt.xticks(rotation=45, ha="right")                              # Rotate the month labels so they fit nicely.
        plt.tight_layout()                                               # Tidy margins.
        plt.savefig(chart2_path, dpi=150)                                # Save the chart.
        plt.close()
        print(f"Saved timeline chart to {chart2_path}")
    else:
        print("Timeline chart skipped — no usable dates were found.")    # Be clear about why nothing was drawn.

    # PART C.11 — TERMINAL SUMMARY
    print("\n" + "=" * 70)
    print("STRATEGIC SUMMARY")
    print("=" * 70)
    print(f"Total articles collected: {len(df)}")                        # Headline number.
    if not theme_counts.empty:                                           # Guard against an unlikely empty case.
        most_common_theme = theme_counts.idxmax()                        # idxmax returns the label with the highest count.
        most_common_count = theme_counts.max()                           # The count itself.
        least_common_theme = theme_counts.idxmin()                       # The label with the lowest count.
        least_common_count = theme_counts.min()                          # The lowest count.
        print(f"Most common theme:  {most_common_theme} ({most_common_count} articles)")
        print(f"Least common theme: {least_common_theme} ({least_common_count} articles)")

        # For the strategic interpretation we report the dominant *real* theme
        # (excluding "Other"), because "Other is biggest" is not an insight.
        strategic_only = theme_counts.drop("Other", errors="ignore")     # Drop "Other" if it exists.
        if not strategic_only.empty:                                     # If at least one real theme is left...
            dominant_theme = strategic_only.idxmax()                     # ...use it as the dominant strategic theme.
            dominant_count = strategic_only.max()
            other_count = int(theme_counts.get("Other", 0))               # How many didn't classify.
            print(f"Dominant strategic theme (excluding 'Other'): {dominant_theme} ({dominant_count} articles)")
            if other_count:
                print(f"  ({other_count} articles did not match any of the six strategic themes)")
        else:
            dominant_theme = most_common_theme                           # Fallback if everything is "Other".

        # A small templated interpretation paragraph, written so the user can
        # paste it straight into a portfolio writeup or interview prep.
        interpretations = {
            "Partnership":          "C2FO is leaning heavily on partnerships with banks and platforms to extend reach.",
            "Geographic Expansion": "C2FO is prioritising international growth, telling a story of expanding into new markets.",
            "Product Launch":       "C2FO is positioning itself as a product-led innovator in working capital.",
            "Thought Leadership":   "C2FO is investing in earned-media and research-driven thought leadership over hard product news.",
            "ESG / Sustainability": "C2FO is leading with sustainable-finance messaging, likely to win mandates from ESG-conscious enterprises.",
            "Awards / Recognition": "C2FO is amplifying third-party validation (awards, rankings) to build credibility with enterprise buyers.",
            "Other":                "C2FO's public messaging is fairly diffuse — no single strategic theme dominates the narrative.",
        }
        interpretation = interpretations.get(                            # Look up the interpretation for the dominant strategic theme.
            dominant_theme,
            "C2FO's public messaging shows a mixed strategic focus.",     # Default fallback.
        )
        print("\nInterpretation:")
        print(f"  {interpretation}")
    print("=" * 70)


# Standard Python entry-point guard. The code below only runs when this file
# is executed directly (e.g. `python3 c2fo_tracker.py`), not when it is
# imported by another script.
if __name__ == "__main__":
    main()                                                               # Kick off the whole pipeline.
