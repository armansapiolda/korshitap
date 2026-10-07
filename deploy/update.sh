#!/usr/bin/env bash
# Pull the latest code and restart: sudo bash /opt/korshitap/deploy/update.sh
set -euo pipefail
APP_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

if [ "$(id -u)" -ne 0 ]; then
  echo "Запусти через sudo: sudo bash $0" >&2
  exit 1
fi

"$APP_DIR/deploy/backup.sh"
git -C "$APP_DIR" pull --ff-only
"$APP_DIR/.venv/bin/pip" install -r "$APP_DIR/requirements.txt"
chown -R korshi:korshi "$APP_DIR"
chmod 600 "$APP_DIR/.env"
systemctl restart korshi-tap
sleep 3
systemctl --no-pager status korshi-tap | head -5
echo "Обновлено. Логи: sudo journalctl -u korshi-tap -f"
