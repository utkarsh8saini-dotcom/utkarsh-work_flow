# run_public.ps1 — run the Flight Price Tracker and expose it to your phone
# (anywhere, over cellular) through a secure Cloudflare tunnel.
#
#   1) one-time:  winget install --id Cloudflare.cloudflared
#   2) set APP_TOKEN=<a secret> in .env  (protects the public URL)
#   3) run:       powershell -ExecutionPolicy Bypass -File .\run_public.ps1
#
$ErrorActionPreference = "Stop"
Set-Location -Path $PSScriptRoot

# --- read APP_TOKEN from .env (required before exposing publicly) ---
$token = ""
if (Test-Path ".env") {
  foreach ($line in Get-Content ".env") {
    if ($line -match "^\s*APP_TOKEN\s*=\s*(.+?)\s*$") { $token = $Matches[1].Trim() }
  }
}
if (-not $token) {
  Write-Host "APP_TOKEN is blank in .env." -ForegroundColor Yellow
  Write-Host "Set APP_TOKEN=<some-secret-string> in .env first so the public URL isn't open to everyone, then re-run." -ForegroundColor Yellow
  exit 1
}

# --- ensure cloudflared is installed ---
if (-not (Get-Command cloudflared -ErrorAction SilentlyContinue)) {
  Write-Host "cloudflared not found. Install it once with:" -ForegroundColor Yellow
  Write-Host "    winget install --id Cloudflare.cloudflared" -ForegroundColor Cyan
  Write-Host "(or: scoop install cloudflared)  then re-run this script." -ForegroundColor Yellow
  exit 1
}

# --- start the server (0.0.0.0 => reachable on LAN and by the tunnel) if not already up ---
if (-not (Get-NetTCPConnection -LocalPort 8000 -State Listen -ErrorAction SilentlyContinue)) {
  Write-Host "Starting Flight Tracker on :8000 ..." -ForegroundColor Green
  Start-Process -WindowStyle Hidden -FilePath "uv" -ArgumentList "run","main.py","serve","--host","0.0.0.0","--port","8000"
  Start-Sleep -Seconds 4
} else {
  Write-Host "Server already listening on :8000." -ForegroundColor Green
}

Write-Host ""
Write-Host "Opening a secure Cloudflare tunnel — watch for a https://XXXX.trycloudflare.com line below." -ForegroundColor Green
Write-Host "On your phone open that URL with your token appended, e.g.:" -ForegroundColor Green
Write-Host "    https://XXXX.trycloudflare.com/?token=$token" -ForegroundColor Cyan
Write-Host "(after the first visit the token is remembered on that phone)"  -ForegroundColor DarkGray
Write-Host ""

cloudflared tunnel --url http://localhost:8000
