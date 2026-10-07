#!/usr/bin/env bash
# One-time server setup (Ubuntu 22.04/24.04). Run from the cloned repo:
#   sudo bash /opt/korshitap/deploy/setup.sh
# See DEPLOY.md for the full step-by-step guide.
set -euo pipefail

APP_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
APP_USER=korshi
DEPLOY_KEY=/root/.ssh/korshi_deploy

if [ "$(id -u)" -ne 0 ]; then
  echo "Запусти через sudo: sudo bash $0" >&2
  exit 1
fi

echo "==> Пакеты"
apt-get update -y
apt-get install -y python3-venv python3-pip git

echo "==> Пользователь $APP_USER"
id -u "$APP_USER" >/dev/null 2>&1 || useradd --system --create-home --shell /usr/sbin/nologin "$APP_USER"

echo "==> Git (обновления через deploy key)"
git config --global --add safe.directory "$APP_DIR"
if [ -f "$DEPLOY_KEY" ]; then
  git -C "$APP_DIR" config core.sshCommand "ssh -i $DEPLOY_KEY -o StrictHostKeyChecking=accept-new"
fi

echo "==> Python-окружение"
python3 -m venv "$APP_DIR/.venv"
"$APP_DIR/.venv/bin/pip" install --upgrade pip
"$APP_DIR/.venv/bin/pip" install -r "$APP_DIR/requirements.txt"

echo "==> .env"
if [ ! -f "$APP_DIR/.env" ]; then
  cp "$APP_DIR/.env.example" "$APP_DIR/.env"
  # On Google Cloud the VM's service account is used for Vertex AI, no key file needed
  sed -i 's|^GOOGLE_APPLICATION_CREDENTIALS=.*|GOOGLE_APPLICATION_CREDENTIALS=|' "$APP_DIR/.env"
  echo "    Создан $APP_DIR/.env из примера — заполни его (см. DEPLOY.md)."
fi
chown -R "$APP_USER:$APP_USER" "$APP_DIR"
chmod 600 "$APP_DIR/.env"

echo "==> Автозапуск (systemd)"
install -m 644 "$APP_DIR/deploy/korshi-tap.service" /etc/systemd/system/korshi-tap.service
systemctl daemon-reload
systemctl enable korshi-tap

echo "==> Ежедневная резервная копия базы (03:30)"
chmod +x "$APP_DIR/deploy/backup.sh" "$APP_DIR/deploy/update.sh"
echo "30 3 * * * root $APP_DIR/deploy/backup.sh" > /etc/cron.d/korshi-tap-backup

if grep -q "your_telegram_bot_token_here" "$APP_DIR/.env"; then
  echo
  echo "Готово, но бот ещё не запущен: в .env нет токена."
  echo "  1) sudo nano $APP_DIR/.env"
  echo "  2) sudo systemctl start korshi-tap"
else
  systemctl restart korshi-tap
  echo
  echo "Готово, бот запущен. Логи: sudo journalctl -u korshi-tap -f"
fi
