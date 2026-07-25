#!/usr/bin/env python3
"""
BFI IMAX - "The Odyssey" screening monitor.

Watches the BFI IMAX booking page and pushes a notification to your phone
(via ntfy.sh) the moment NEW screenings appear or a sold-out screening
becomes available again - so you can jump straight to the site and book.

How it works
------------
The BFI booking page (AudienceView) renders its showtimes into the page HTML,
but only inside a paginated widget that needs a live session token. A plain,
anonymous request sees nothing - which is why this script uses a real browser
session. It tries a fast requests-based fetch first and automatically falls
back to a headless browser (Playwright) if the fast path is blocked.

Each run it builds the full set of screenings (date/time + Sold out / Available),
compares it against the set it saw last time (stored in state.json), and only
notifies you when something actually changed.

Env vars
--------
NTFY_TOPIC   (required)  Your private ntfy topic, e.g. "bfi-odyssey-a8f3k2".
                         Install the free ntfy app, subscribe to this topic.
NTFY_SERVER  (optional)  Default https://ntfy.sh
STATE_FILE   (optional)  Default state.json (next to this script)
MAX_PAGES    (optional)  Safety cap on pagination. Default 60.
FIRST_RUN_ALERT (optional) "1" to also alert on the very first run. Default off
                         (first run just records the baseline silently).
"""

from __future__ import annotations

import json
import os
import re
import sys
import time
from datetime import datetime, date
from pathlib import Path
from urllib.parse import urljoin, urlparse, parse_qs, urlencode, urlunparse

import requests
from bs4 import BeautifulSoup

# --------------------------------------------------------------------------- #
# Config
# --------------------------------------------------------------------------- #
ARTICLE_URL = (
    "https://whatson.bfi.org.uk/imax/Online/default.asp"
    "?BOparam::WScontent::loadArticle::permalink=odyssey-the-film-imax-70mm-2026"
)
BOOKING_URL = ARTICLE_URL  # where the user goes to book

BASE = os.path.dirname(os.path.abspath(__file__))
STATE_FILE = Path(os.environ.get("STATE_FILE", os.path.join(BASE, "state.json")))
NTFY_TOPIC = os.environ.get("NTFY_TOPIC", "").strip()
NTFY_SERVER = os.environ.get("NTFY_SERVER", "https://ntfy.sh").rstrip("/")
MAX_PAGES = int(os.environ.get("MAX_PAGES", "60"))
FIRST_RUN_ALERT = os.environ.get("FIRST_RUN_ALERT", "0") == "1"

BROWSER_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-GB,en;q=0.9",
}

# Matches "Sunday 19 July 2026 20:20"
DATE_RE = re.compile(r"[A-Za-z]+day\s+\d{1,2}\s+[A-Za-z]+\s+\d{4}\s+\d{2}:\d{2}")


# --------------------------------------------------------------------------- #
# Parsing (shared by both fetch paths)
# --------------------------------------------------------------------------- #
def parse_items_from_html(html: str) -> list[dict]:
    """Extract screening rows from a page of result HTML."""
    soup = BeautifulSoup(html, "html.parser")
    items = []
    for box in soup.select(".result-box-item"):
        sd = box.select_one(".start-date")
        if not sd:
            continue
        when = sd.get_text(strip=True)
        if not DATE_RE.search(when):
            continue
        link = box.select_one(".item-link")
        classes = " ".join(link.get("class", [])) if link else ""
        text = box.get_text(" ", strip=True).lower()
        sold_out = ("soldout" in classes) or ("sold out" in text)
        venue_el = box.select_one(".item-venue")
        venue = venue_el.get_text(strip=True) if venue_el else "BFI IMAX"
        items.append(
            {"when": when, "venue": venue,
             "status": "Sold out" if sold_out else "Available"}
        )
    return items


def total_pages_from_html(html: str) -> int:
    """Read the highest page number from the pagination control."""
    soup = BeautifulSoup(html, "html.parser")
    nums = []
    for a in soup.select("a"):
        t = a.get_text(strip=True)
        if t.isdigit():
            nums.append(int(t))
    return max(nums) if nums else 1


def page_url_template(html: str, base_url: str):
    """
    Find a numbered pagination link and return a function that builds the URL
    for an arbitrary page by swapping the current_page value.
    """
    soup = BeautifulSoup(html, "html.parser")
    page_param = None
    template_href = None
    for a in soup.select("a"):
        if not a.get_text(strip=True).isdigit():
            continue
        href = a.get("href")
        if not href:
            continue
        full = urljoin(base_url, href)
        q = parse_qs(urlparse(full).query, keep_blank_values=True)
        for k in q:
            if k.endswith("current_page"):
                page_param = k
                template_href = full
                break
        if page_param:
            break

    if not page_param:
        return None

    def build(page_num: int) -> str:
        parts = urlparse(template_href)
        q = parse_qs(parts.query, keep_blank_values=True)
        q[page_param] = [str(page_num)]
        new_query = urlencode({k: v[0] for k, v in q.items()}, safe=":=")
        return urlunparse(parts._replace(query=new_query))

    return build


# --------------------------------------------------------------------------- #
# Fetch path 1: fast, session-based requests
# --------------------------------------------------------------------------- #
def fetch_with_requests() -> list[dict] | None:
    try:
        s = requests.Session()
        s.headers.update(BROWSER_HEADERS)
        r = s.get(ARTICLE_URL, timeout=30)
        r.raise_for_status()
        html = r.text
        first = parse_items_from_html(html)
        if not first:
            return None  # blocked / empty -> let caller fall back

        all_items = {i["when"]: i for i in first}
        build = page_url_template(html, str(r.url))
        pages = min(total_pages_from_html(html), MAX_PAGES)
        if build and pages > 1:
            for p in range(2, pages + 1):
                try:
                    rp = s.get(build(p), timeout=30)
                    rp.raise_for_status()
                    for i in parse_items_from_html(rp.text):
                        all_items[i["when"]] = i
                    time.sleep(0.4)
                except requests.RequestException:
                    continue
        return list(all_items.values())
    except Exception as e:  # noqa: BLE001
        print(f"[requests] failed: {e}", file=sys.stderr)
        return None


# --------------------------------------------------------------------------- #
# Fetch path 2: reliable, headless browser (Playwright)
# --------------------------------------------------------------------------- #
def fetch_with_playwright() -> list[dict] | None:
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        print("[playwright] not installed; skipping fallback", file=sys.stderr)
        return None

    try:
        with sync_playwright() as pw:
            browser = pw.chromium.launch(headless=True)
            page = browser.new_page(user_agent=BROWSER_HEADERS["User-Agent"])
            page.goto(ARTICLE_URL, wait_until="networkidle", timeout=60000)
            try:
                page.wait_for_selector(".result-box-item", timeout=15000)
            except Exception:  # noqa: BLE001
                pass

            all_items: dict[str, dict] = {}
            seen_pages = 0
            while seen_pages < MAX_PAGES:
                html = page.content()
                for i in parse_items_from_html(html):
                    all_items[i["when"]] = i
                seen_pages += 1
                # click the "next page" control if present and enabled
                nxt = page.query_selector("a:has-text('»'), a[title*='Next'], .next a")
                if not nxt:
                    break
                try:
                    before = page.query_selector(".start-date")
                    before_txt = before.inner_text() if before else ""
                    nxt.click()
                    page.wait_for_timeout(1200)
                    after = page.query_selector(".start-date")
                    after_txt = after.inner_text() if after else ""
                    if after_txt == before_txt:
                        break  # page didn't advance
                except Exception:  # noqa: BLE001
                    break
            browser.close()
            return list(all_items.values()) or None
    except Exception as e:  # noqa: BLE001
        print(f"[playwright] failed: {e}", file=sys.stderr)
        return None


# --------------------------------------------------------------------------- #
# State + notifications
# --------------------------------------------------------------------------- #
def load_state() -> dict:
    if STATE_FILE.exists():
        try:
            return json.loads(STATE_FILE.read_text())
        except Exception:  # noqa: BLE001
            pass
    return {"screenings": {}, "consecutive_empty": 0}


def save_state(state: dict) -> None:
    STATE_FILE.write_text(json.dumps(state, indent=2, ensure_ascii=False))


def parse_when_date(when: str) -> date | None:
    m = re.search(r"(\d{1,2})\s+([A-Za-z]+)\s+(\d{4})", when)
    if not m:
        return None
    try:
        return datetime.strptime(
            f"{m.group(1)} {m.group(2)} {m.group(3)}", "%d %B %Y"
        ).date()
    except ValueError:
        return None


def notify(title: str, message: str, priority: str = "default",
           tags: str = "clapper", click: str = BOOKING_URL) -> None:
    if not NTFY_TOPIC:
        print("NTFY_TOPIC not set - printing instead:\n"
              f"  {title}\n  {message}")
        return
    try:
        requests.post(
            f"{NTFY_SERVER}/{NTFY_TOPIC}",
            data=message.encode("utf-8"),
            headers={
                "Title": title,
                "Priority": priority,
                "Tags": tags,
                "Click": click,
            },
            timeout=20,
        )
    except requests.RequestException as e:
        print(f"[ntfy] failed to send: {e}", file=sys.stderr)


# --------------------------------------------------------------------------- #
# Main
# --------------------------------------------------------------------------- #
def main() -> int:
    items = fetch_with_requests()
    if not items:
        items = fetch_with_playwright()

    state = load_state()
    prev = state.get("screenings", {})

    # Safeguard: page returned nothing but we had screenings before ->
    # the monitor may be blocked or the page changed. Warn once.
    if not items:
        state["consecutive_empty"] = state.get("consecutive_empty", 0) + 1
        if prev and state["consecutive_empty"] == 3:
            notify(
                "BFI Odyssey monitor needs a look",
                "Couldn't read any screenings for 3 checks in a row - the page "
                "may have changed or be blocking automated reads. Check it manually.",
                priority="high", tags="warning",
            )
        save_state(state)
        print("No screenings parsed this run.")
        return 0

    state["consecutive_empty"] = 0
    current = {i["when"]: i["status"] for i in items}

    new_screenings = [w for w in current if w not in prev]
    newly_available = [
        w for w, st in current.items()
        if st == "Available" and prev.get(w) == "Sold out"
    ]

    first_run = not prev

    def sort_key(w):  # chronological-ish ordering for the message
        d = parse_when_date(w)
        return (d or date.max, w)

    if first_run and not FIRST_RUN_ALERT:
        print(f"Baseline recorded: {len(current)} screenings. No alert on first run.")
    elif new_screenings or newly_available:
        lines = []
        if new_screenings:
            lines.append(f"NEW screenings added ({len(new_screenings)}):")
            for w in sorted(new_screenings, key=sort_key)[:20]:
                lines.append(f"  - {w}  [{current[w]}]")
        if newly_available:
            lines.append(f"Now AVAILABLE (was sold out) ({len(newly_available)}):")
            for w in sorted(newly_available, key=sort_key)[:20]:
                lines.append(f"  - {w}")
        lines.append("\nBook now at the BFI IMAX site.")
        notify(
            "The Odyssey - new BFI IMAX screenings!",
            "\n".join(lines),
            priority="urgent",
            tags="clapper,fire",
        )
        print("Alert sent:\n" + "\n".join(lines))
    else:
        print(f"No change. {len(current)} screenings tracked, "
              f"{sum(1 for s in current.values() if s=='Available')} available.")

    # Save updated state (prune screenings whose date is in the past)
    today = date.today()
    merged = dict(prev)
    merged.update(current)
    pruned = {}
    for w, st in merged.items():
        d = parse_when_date(w)
        if d is None or d >= today:
            pruned[w] = current.get(w, st)
    state["screenings"] = pruned
    state["last_checked"] = datetime.now().isoformat(timespec="seconds")
    save_state(state)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
