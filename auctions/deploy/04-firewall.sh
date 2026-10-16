#!/usr/bin/env bash
set -euo pipefail
source "$(dirname "$0")/config.sh"
[[ $EUID -eq 0 ]] || { echo "Запускайте через sudo"; exit 1; }
ROLE=${1:?usage: sudo ./04-firewall.sh app|db}

ufw default deny incoming
ufw default allow outgoing
ufw allow in on "$INTERNAL_IF" to any port 22 proto tcp     # SSH (только внутренняя сеть)

case "$ROLE" in
  app) ufw allow in on "$INTERNAL_IF" to any port "$APP_PORT" proto tcp ;;
  db)  ufw allow from "$APP_IP" to any port 5432 proto tcp ;;   # БД только для сервера приложения
  *)   echo "Роль: app или db"; exit 1 ;;
esac

ufw --force enable
ufw status verbose
