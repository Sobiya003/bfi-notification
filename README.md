# BFI IMAX — "The Odyssey" screening alert

Pushes a notification to your phone the moment BFI IMAX adds new *Odyssey*
screenings (or a sold-out show frees up), so you can jump straight in and book.

Everything here is **free**: notifications via [ntfy.sh](https://ntfy.sh)
(no account needed) and unattended scheduling via GitHub Actions.

## What it does

Every 15 minutes it reads the BFI booking page, builds the full list of
screenings and their status, and compares it to the previous run. It only
pings you when something actually **changes** — a new date/time appears, or a
sold-out screening becomes available. No spam.

The BFI page hides its showtimes behind a session-gated, paginated widget (a
plain request sees nothing), so the script uses a real browser session — a fast
`requests` session first, falling back to a headless browser automatically if
needed.

## Notifications: set up ntfy (2 minutes, free)

1. Install the **ntfy** app (iOS App Store / Google Play).
2. Pick a private, hard-to-guess topic name, e.g. `bfi-odyssey-7h3k9x`
   (anyone who knows the topic can send you notifications, so keep it random).
3. In the app, tap **+** and subscribe to that exact topic.

That's it — the script POSTs to `https://ntfy.sh/<your-topic>` and it lands on
your phone. Tapping the notification opens the BFI booking page directly.

## Option A — Free cloud scheduling (recommended, always-on)

Runs in GitHub's cloud, so your computer doesn't need to be on.

1. Create a **public** GitHub repo (public = unlimited free Actions minutes;
   `state.json` only contains public showtimes).
2. Upload these files, keeping the folder layout:
   ```
   bfi_odyssey_monitor.py
   requirements.txt
   .github/workflows/monitor.yml
   ```
3. In the repo: **Settings → Secrets and variables → Actions → New repository
   secret**. Name it `NTFY_TOPIC`, value = your topic (e.g. `bfi-odyssey-7h3k9x`).
4. Open the **Actions** tab, enable workflows, and click **Run workflow** once
   to record the baseline. From then on it runs itself every 15 minutes.

To change frequency, edit the `cron` line in `monitor.yml`.

## Option B — Run on your own machine

Works while your computer is on. Good for a quick test.

```bash
pip install -r requirements.txt
python -m playwright install chromium        # only needed for the fallback
export NTFY_TOPIC="bfi-odyssey-7h3k9x"
python bfi_odyssey_monitor.py
```

Schedule it with `cron` (Mac/Linux), e.g. every 15 minutes:

```
*/15 * * * * cd /path/to/folder && NTFY_TOPIC=bfi-odyssey-7h3k9x /usr/bin/python3 bfi_odyssey_monitor.py >> monitor.log 2>&1
```

## Testing it works

Set `FIRST_RUN_ALERT=1` for a single run to force a notification on the first
check (confirms the ntfy pipe works end-to-end), then unset it.

```bash
FIRST_RUN_ALERT=1 NTFY_TOPIC=bfi-odyssey-7h3k9x python bfi_odyssey_monitor.py
```

## Notes

- First run is silent by default — it just records the current screenings as a
  baseline. You get pinged on *changes* after that.
- If the page returns no screenings 3 checks in a row (e.g. BFI changed their
  site or started blocking), it sends a one-off "needs a look" warning so you're
  never silently left in the dark.
- Booking still happens on the BFI site — this only tells you *when* to go.
