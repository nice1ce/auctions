#!/usr/bin/env bash
set -euo pipefail
source "$(dirname "$0")/config.sh"
[[ $EUID -eq 0 ]] || { echo "Запускайте через sudo"; exit 1; }
ADMIN=${SUDO_USER:?Запускайте через sudo от административного пользователя, не от root}
DEPLOY_DIR=$(cd "$(dirname "$0")" && pwd)

apt-get update -qq
apt-get install -y git python3-venv python3-pip postgresql-client curl

# --- системный пользователь без входа в систему ---
id "$APP_USER" &>/dev/null || \
  adduser --system --group --home "$APP_DIR" --shell /usr/sbin/nologin "$APP_USER"
install -d -o "$ADMIN" -g "$APP_USER" -m 750 "$APP_DIR"

# --- код: владелец админ, группа сервиса читает ---
if [[ -d $APP_DIR/app/.git ]]; then
  sudo -u "$ADMIN" git -C "$APP_DIR/app" pull --ff-only
else
  sudo -u "$ADMIN" git clone "$REPO_URL" "$APP_DIR/app"
fi

# --- Python 3.12 (как в проекте) через uv + venv ---
if [[ ! -x $APP_DIR/venv/bin/python ]]; then
  sudo -u "$ADMIN" python3 -m venv /tmp/uvtool
  sudo -u "$ADMIN" /tmp/uvtool/bin/pip install -q uv
  sudo -u "$ADMIN" env UV_PYTHON_INSTALL_DIR="$APP_DIR/python" \
    /tmp/uvtool/bin/uv venv --seed --python 3.12 "$APP_DIR/venv"
  rm -rf /tmp/uvtool
fi
sudo -u "$ADMIN" "$APP_DIR/venv/bin/pip" install -q -r "$APP_DIR/app/requirements.txt"
chown -R "$ADMIN:$APP_USER" "$APP_DIR"
chmod 750 "$APP_DIR"

# --- настройки отдельно от кода ---
install -d -m 750 -o root -g "$APP_USER" "$(dirname "$ENV_FILE")"
if [[ ! -f $ENV_FILE ]]; then
  if [[ -z ${DB_APP_PASSWORD:-} ]]; then
    read -rsp "Пароль роли $DB_APP_ROLE: " DB_APP_PASSWORD; echo
  fi
  ( umask 077
    sed -e "s|__DB_APP_ROLE__|$DB_APP_ROLE|" \
        -e "s|__DB_APP_PASSWORD__|$DB_APP_PASSWORD|" \
        -e "s|__DB_IP__|$DB_IP|" \
        -e "s|__DB_NAME__|$DB_NAME|" \
        "$DEPLOY_DIR/auctions.env.template" > "$ENV_FILE" )
  chown root:"$APP_USER" "$ENV_FILE"
  chmod 640 "$ENV_FILE"
fi

# --- systemd ---
install -m 644 "$DEPLOY_DIR/auctions.service" /etc/systemd/system/auctions.service
systemctl daemon-reload
systemctl enable --now auctions
sleep 2
systemctl --no-pager status auctions | head -n 8
curl -s "http://127.0.0.1:$APP_PORT/health"; echo
echo "Не забудьте выполнить миграции: ./05-migrate.sh, затем sudo systemctl restart auctions"
