#!/usr/bin/env bash
set -euo pipefail
source "$(dirname "$0")/config.sh"

read -rsp "Пароль роли $DB_MIGRATOR_ROLE: " PW; echo
cd "$APP_DIR/app"
DATABASE_URL="postgresql+psycopg://$DB_MIGRATOR_ROLE:$PW@$DB_IP:5432/$DB_NAME" \
  "$APP_DIR/venv/bin/alembic" upgrade head
unset PW
