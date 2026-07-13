# Flight Price Tracker — container image for cloud hosting (Fly.io / Render / Railway).
FROM python:3.12-slim

WORKDIR /app

COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# History (flight_prices.xlsx + watches.json) lives on a mounted volume so it
# survives restarts/redeploys.
ENV DATA_DIR=/data \
    PYTHONPATH=/app \
    PYTHONUNBUFFERED=1 \
    WATCH_INTERVAL_MINUTES=30
RUN mkdir -p /data

EXPOSE 8000

# waitress = single process, multithreaded => exactly ONE background sampler and
# ONE file writer (safe). Binds the platform's $PORT (default 8000).
CMD ["sh", "-c", "waitress-serve --host=0.0.0.0 --port=${PORT:-8000} --call web.server:create_app"]
