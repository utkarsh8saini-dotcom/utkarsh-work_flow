#!/usr/bin/env bash
# One-shot setup for a FREE Oracle Cloud "Always Free" Ubuntu VM.
# Run this ON the VM, from inside the project folder (Dockerfile + .env present).
#   bash setup-oracle.sh
set -euo pipefail

APP_DIR="$(pwd)"
DATA_DIR="/opt/flightdata"
NAME="flighttracker"

echo "==> Installing Docker (if missing)…"
if ! command -v docker >/dev/null 2>&1; then
  sudo apt-get update -y
  sudo apt-get install -y ca-certificates curl
  curl -fsSL https://get.docker.com | sudo sh
  sudo usermod -aG docker "$USER" || true
fi

echo "==> Opening TCP 80 on the VM's local firewall…"
sudo iptables -I INPUT 6 -m state --state NEW -p tcp --dport 80 -j ACCEPT 2>/dev/null || true
sudo netfilter-persistent save 2>/dev/null || true

[ -f "$APP_DIR/Dockerfile" ] || { echo "!! No Dockerfile here — cd into the project folder and re-run."; exit 1; }
[ -f "$APP_DIR/.env" ]      || { echo "!! No .env here — create one (see .env.example): APP_TOKEN, SMTP_*, ALERT_TO."; exit 1; }

echo "==> Building image…"
sudo docker build -t "$NAME" "$APP_DIR"

echo "==> (Re)starting container: port 80, auto-restart, persistent /data …"
sudo mkdir -p "$DATA_DIR"
sudo docker rm -f "$NAME" 2>/dev/null || true
sudo docker run -d --name "$NAME" --restart unless-stopped \
  -p 80:8000 -v "$DATA_DIR:/data" --env-file "$APP_DIR/.env" "$NAME"

IP="$(curl -s ifconfig.me || echo '<VM-PUBLIC-IP>')"
echo ""
echo "==================================================================="
echo " Done. On your phone open:  http://${IP}/?token=<your APP_TOKEN>"
echo " If it doesn't load, add an Ingress rule for TCP 80 in the VCN"
echo " Security List (Networking > VCN > Security Lists) for 0.0.0.0/0."
echo "==================================================================="
