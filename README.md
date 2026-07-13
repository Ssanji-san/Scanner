# Minervini Trend Template Scanner

Free, automated nightly scan of the US stock market against Mark Minervini's
Trend Template (8 conditions + a volume clause), with heuristic cup-base /
cheat-entry detection, a static web dashboard, and email alerts when
something new shows up. Runs entirely on free tiers: GitHub Actions +
GitHub Pages + Alpaca market data + Gmail.

> **This finds candidates, not buy signals.** Minervini's actual method
> (SEPA) layers fundamentals, base analysis, and precise entries/exits on
> top of this screen. Cup detection is best-effort pattern matching — always
> check the chart. Not financial advice.

## The 9 conditions

1. Price above the 150-day and 200-day MA
2. 150-day MA above 200-day MA
3. 200-day MA rising for at least 1 month (★ bonus flag at 5 months)
4. 50-day MA above the 150-day and 200-day MA
5. Price above the 50-day MA
6. Price at least 30% above its 52-week low
7. Price within 25% of its 52-week high
8. RS rating ≥ 70 (percentile of IBD-style weighted 12-month return,
   computed within the scanned universe — an approximation of IBD's number)
9. Volume ≥ 20-day EMA of volume (from the Chartink "with volume" variant)

Thresholds, SMA/EMA choice, and universe floors ($1 price, 300k avg volume)
live in `scanner/config.py`.

## Cup / cheat-entry detection

For every scanned stock the scanner looks for a cup base: a major high, a
12–50% correction with a rounded (not V) bottom, a recovering right side,
and a tight low-volume pause. The pause's high is the **pivot**; its
position within the cup names the entry zone — lower third **Low Cheat**,
middle **Mid Cheat**, upper **Cheat**. States: `forming` (watch the pivot)
and `triggered` (pivot broke today). Every detection has a confidence score
and is drawn on the dashboard sparkline for a human sanity check.

## Alerts

An email is sent only when there is something to say: a stock newly passing
all 9 conditions, a new cup setup, or a cup breakout. No spam on quiet days.

## Local usage

```powershell
python -m venv .venv
.venv\Scripts\pip install -r requirements.txt
.venv\Scripts\python -m pytest            # 43 tests
$env:ALPACA_KEY = "..."; $env:ALPACA_SECRET = "..."
.venv\Scripts\python -m scanner.main --limit 300   # small real scan
.venv\Scripts\python -m scanner.main               # full universe (~5 min)
python -m http.server 8123 --directory docs        # dashboard at localhost:8123
```

Without Gmail credentials the alert prints to the console (dry run) instead
of sending.

## One-time setup (all free)

### 1. Alpaca (market data)
1. Sign up at https://alpaca.markets (choose **paper trading** — no deposit,
   no real money, we only use market data).
2. Dashboard → **API Keys** → generate. Note the **Key ID** and **Secret**.

### 2. GitHub repository + Pages (hosting + automation)
1. Create a **public** repo (public = free GitHub Pages) and push this project.
2. Repo **Settings → Pages** → Source: *Deploy from a branch* →
   Branch `main`, folder `/docs`. Your dashboard URL becomes
   `https://<user>.github.io/<repo>/`.
3. **Settings → Secrets and variables → Actions**:
   - Secrets: `ALPACA_KEY`, `ALPACA_SECRET`, `GMAIL_USER` (your Gmail
     address), `GMAIL_APP_PASSWORD` (next step)
   - Variables: `DASHBOARD_URL` = your Pages URL
4. The workflow (`.github/workflows/scan.yml`) then runs every weeknight
   (~22:00 New York) and can be run on demand from the **Actions** tab
   (*nightly-scan → Run workflow*).

### 3. Gmail app password (alerts)
1. Enable **2-Step Verification** on your Google account
   (https://myaccount.google.com/security).
2. Then create an **App password** (https://myaccount.google.com/apppasswords),
   app "Mail" — a 16-character code. That code is `GMAIL_APP_PASSWORD`.
   Your normal password is never used or stored.

## Honest limitations

- Data is Alpaca's free IEX feed: daily closes can differ marginally from
  consolidated-tape closes; irrelevant for 150/200-day MAs.
- RS percentile is computed within our filtered universe, so it differs a
  bit from IBD's official RS rating.
- Cup detection is heuristic; expect false positives, use the confidence
  score and your eyes. Real-world confidences run lower than the demo data's.
- The repo (including scan results) is public — that's what makes Pages
  free. Keys stay in GitHub Secrets and are never in the repo.

## Layout

```
scanner/    config, conditions, rs_rating, patterns (cups), data (Alpaca),
            universe, report (diff/JSON), emailer, main (entrypoint)
tests/      pytest suite (43 tests) + synthetic bar fixtures
docs/       static dashboard (GitHub Pages) + data/latest.json
scripts/    make_demo_data.py — fixture data for dashboard preview
```
