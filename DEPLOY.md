# Deploying the Flight Price Tracker to the cloud (24/7, phone-accessible)

This runs the tracker on an always-on server so prices keep updating and you can open it
from your phone anywhere — even with your laptop off.

## Read first — two honest trade-offs

1. **Always-on costs a little.** The 24/7 background sampler only works while the server is
   actually running. Free tiers **sleep when idle** (Render free sleeps after ~15 min; the
   sampler then pauses until someone opens the page). For genuine round-the-clock tracking you
   need an always-on instance — roughly **$2–7/month** (Fly small machine, or Render "starter").
2. **Cloud IPs can get throttled by Google Flights.** `fast-flights` scrapes Google Flights.
   From a datacenter IP, Google blocks/captchas more than from your home connection, so some
   samples may come back empty. If that happens, set an `HTTPS_PROXY` secret (any residential
   proxy) — the app already honors it. Your **local + tunnel** setup (run_public.ps1) scrapes
   more reliably; the cloud option trades a bit of scrape-reliability for laptop-off uptime.

Everything below is prepared already: `Dockerfile`, `requirements.txt`, `fly.toml`,
`render.yaml`, `.dockerignore`, and a `/healthz` check.

---

## Option A — Fly.io (recommended: deploy straight from this folder, no GitHub)

```powershell
# 1) Install the CLI (once) and sign in (needs a free account + card on file for always-on)
winget install --id Fly.Flyctl
fly auth login

# 2) From this folder — create the app (keeps the provided fly.toml)
fly launch --no-deploy         # accept name/region or edit fly.toml; say NO to Postgres/Redis

# 3) Persistent history + your secrets
fly volumes create flight_data --size 1 --region sin
fly secrets set APP_TOKEN="pick-a-secret" `
  SMTP_HOST="smtp.gmail.com" SMTP_PORT="587" `
  SMTP_USER="you@gmail.com" SMTP_PASSWORD="your-google-app-password" `
  ALERT_TO="you@gmail.com"

# 4) Ship it
fly deploy
```
Your URL: `https://<app-name>.fly.dev`. On your phone open
`https://<app-name>.fly.dev/?token=pick-a-secret` (the token is remembered after the first visit).

`fly deploy` builds on Fly's remote builder — **you don't need Docker installed locally.**

---

## Option B — Render (Git-based blueprint)

1. Push this repo to your own GitHub (see below), then in Render: **New + → Blueprint → pick the repo**.
   It reads `render.yaml`.
2. In the dashboard, fill the `sync:false` secrets: `APP_TOKEN`, `SMTP_HOST`, `SMTP_USER`,
   `SMTP_PASSWORD`, `ALERT_TO`.
3. Deploy. URL: `https://<name>.onrender.com` → open `.../?token=<APP_TOKEN>` on your phone.

> Free plan **sleeps** (sampler pauses). Choose the **starter** plan (set in `render.yaml`) for
> always-on + the persistent `/data` disk.

Push to GitHub (for Option B):
```powershell
gh repo create flight-price-tracker --private --source . --push
```

---

## Using it from your phone
- Open the URL with `?token=<APP_TOKEN>` once; after that it just works on that device.
- Track a fare: open any row → **Price Watch** → set **alert ≤ price** → **◉ Watch**.
- The server re-samples every `WATCH_INTERVAL_MINUTES` (default 30) around the clock and
  **emails you** when a watched fare drops to/below your threshold.

## Environment variables (set as host secrets, never commit)
| var | purpose |
|-----|---------|
| `APP_TOKEN` | required — locks the public URL (`?token=...`) |
| `SMTP_HOST/PORT/USER/PASSWORD`, `ALERT_FROM`, `ALERT_TO` | email alerts |
| `DEFAULT_CURRENCY` | e.g. `INR` |
| `WATCH_INTERVAL_MINUTES` | sampling cadence (default 30) |
| `DATA_DIR` | `/data` (mounted volume — keeps history across restarts) |
| `HTTPS_PROXY` | optional — if Google Flights throttles the datacenter IP |
