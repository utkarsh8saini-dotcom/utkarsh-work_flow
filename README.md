# Flight Price Tracker Agent

A Python CLI agent that tracks flight prices in near-realtime, finds the cheapest flights, saves all price history to Excel, and analyzes patterns to tell you the best time to buy.

## Features

- **Real-time search** — fetch current prices across airlines for any route/date
- **Price monitoring** — poll every N minutes; get alerted when price drops below your threshold
- **Excel history** — every price fetch is recorded in `data/flight_prices.xlsx` (one sheet per route)
- **Trend analysis** — find the cheapest hour of day, day of week, and price trend over time
- **Dual API support** — Amadeus (preferred, free sandbox) or SerpApi Google Flights (fallback)

## Setup

### 1. Install dependencies (uses [uv](https://docs.astral.sh/uv/))
```bash
# Install uv if you don't have it
curl -LsSf https://astral.sh/uv/install.sh | sh

# Create the virtualenv and install everything from pyproject.toml / uv.lock
uv sync
```

### 2. Configure API keys
```bash
cp .env.example .env
```
Edit `.env` and add at least one set of credentials:

**Option A — Amadeus (recommended, free sandbox)**
1. Sign up at https://developers.amadeus.com/register
2. Create a new app → copy Client ID and Client Secret
3. Set `AMADEUS_CLIENT_ID` and `AMADEUS_CLIENT_SECRET` in `.env`

**Option B — SerpApi (free trial)**
1. Sign up at https://serpapi.com/users/sign_up
2. Copy your API key → set `SERPAPI_KEY` in `.env`

## Usage

Run all commands with `uv run` (no need to activate the virtualenv).

### One-shot search
```bash
uv run main.py search --from DEL --to LHR --date 2026-08-15
uv run main.py search --from JFK --to LAX --date 2026-09-01 --currency USD
```

### Monitor prices (continuous polling)
```bash
# Poll every 30 min, alert if price drops below $500
uv run main.py monitor --from DEL --to LHR --date 2026-08-15 --threshold 500

# Poll every 60 min with custom interval
uv run main.py monitor --from DEL --to LHR --date 2026-08-15 --interval 60

# Poll every 5 minutes (testing)
uv run main.py monitor --from JFK --to LAX --date 2026-09-01 --interval 5 --threshold 300
```
Press **Ctrl+C** to stop monitoring. All prices are saved to Excel automatically.

### Analyze historical data
```bash
uv run main.py analyze --from DEL --to LHR
```
Shows:
- Average price by day of week
- Average price by hour of day (when data was fetched)
- Daily minimum price trend
- Recommendation: best time to buy

## Excel Output

`data/flight_prices.xlsx` — auto-created on first run:

| recorded_at | airline | price | currency | departure | arrival | duration | stops | origin | destination |
|-------------|---------|-------|----------|-----------|---------|----------|-------|--------|-------------|
| 2026-07-11 09:00:00 | Emirates | 342.50 | USD | 2026-08-15 02:30 | ... | 8h 45m | 0 | DEL | LHR |

Each route gets its own sheet (e.g. `DEL→LHR`).

## IATA Airport Codes (examples)

| City | Code |
|------|------|
| Delhi | DEL |
| London Heathrow | LHR |
| New York JFK | JFK |
| Los Angeles | LAX |
| Dubai | DXB |
| Singapore | SIN |
| Mumbai | BOM |
| Paris CDG | CDG |
