#!/usr/bin/env bash
# Copy the SQLite database to /var/backups/korshitap, keep the last 14 copies.
# Does nothing when DATABASE_URL points to Postgres (back it up with pg_dump instead).
set -euo pipefail
APP_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
DB="$APP_DIR/korshi_tap.db"
DEST=/var/backups/korshitap

if grep -qE '^DATABASE_URL=.*postgres' "$APP_DIR/.env" 2>/dev/null; then
  exit 0
fi
[ -f "$DB" ] || exit 0

mkdir -p "$DEST"
OUT="$DEST/korshi_tap-$(date +%Y%m%d-%H%M).db"
# sqlite3 backup API: consistent copy even while the bot is writing
python3 -c "import sqlite3,sys; s=sqlite3.connect(sys.argv[1]); d=sqlite3.connect(sys.argv[2]); s.backup(d); d.close(); s.close()" "$DB" "$OUT"
ls -1t "$DEST"/korshi_tap-*.db | tail -n +15 | xargs -r rm --
echo "Резервная копия: $OUT"
