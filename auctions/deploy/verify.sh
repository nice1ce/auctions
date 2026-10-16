#!/usr/bin/env bash
# Использование: sudo ./verify.sh app|db
source "$(dirname "$0")/config.sh"
ROLE=${1:?usage: sudo ./verify.sh app|db}
FAIL=0
ok()  { echo "[ OK ] $*"; }
bad() { echo "[FAIL] $*"; FAIL=1; }
check() { local d=$1; shift; if "$@" >/dev/null 2>&1; then ok "$d"; else bad "$d"; fi; }

# ---- общее ----
check "root по SSH запрещён"        bash -c "sshd -T | grep -qx 'permitrootlogin no'"
check "вход по паролю запрещён"     bash -c "sshd -T | grep -qx 'passwordauthentication no'"
check "firewall (ufw) активен"      bash -c "ufw status | grep -q 'Status: active'"

# ---- лишние порты: слушающие TCP-сокеты, кроме loopback и разрешённых ----
[[ $ROLE == app ]] && ALLOWED="22|$APP_PORT" || ALLOWED="22|5432"
EXTRA=$(ss -H -tln | awk '{print $4}' | grep -vE '^(127\.|\[::1\]|::1)' \
        | sed 's/.*://' | sort -u | grep -vxE "$ALLOWED" || true)
if [[ -z $EXTRA ]]; then ok "лишних открытых портов нет (разрешены: ${ALLOWED//|/, })"
else bad "лишние порты: $(echo $EXTRA)"; fi

if [[ $ROLE == app ]]; then
  PID=$(systemctl show -p MainPID --value auctions)
  check "служба auctions активна"            systemctl is-active --quiet auctions
  check "автозапуск службы включён"          systemctl is-enabled --quiet auctions
  check "User службы = $APP_USER"            bash -c "[[ \$(systemctl show -p User --value auctions) == $APP_USER ]]"
  check "процесс приложения не от root"      bash -c "[[ \$(ps -o user= -p $PID | tr -d ' ') == $APP_USER ]]"
  check "root не запускает uvicorn"          bash -c "! pgrep -u root -f uvicorn"
  check "Restart=always"                     bash -c "[[ \$(systemctl show -p Restart --value auctions) == always ]]"
  check "файл настроек root:$APP_USER 640"   bash -c "[[ \$(stat -c '%U:%G %a' $ENV_FILE) == 'root:$APP_USER 640' ]]"
  check "$APP_USER не может писать в код"    bash -c "! sudo -u $APP_USER test -w $APP_DIR/app"
  check "health отвечает"                    curl -fs "http://127.0.0.1:$APP_PORT/health"
  check ".env не отслеживается git"          bash -c "[[ -z \$(git -C $APP_DIR/app ls-files | grep -E '(^|/)\.env$') ]]"
  check "в репозитории нет URL с паролем БД" bash -c "! git -C $APP_DIR/app grep -nIE 'postgresql(\+psycopg)?://[^:/@ ]+:[^@ ]+@' -- . ':!.env.example' ':!deploy/auctions.env.template' ':!docs'"
else
  HBA=/etc/postgresql/$(ls /etc/postgresql | sort -V | tail -1)/main/pg_hba.conf
  check "PostgreSQL не слушает 0.0.0.0/*"    bash -c "! ss -tln | grep -E '(0\.0\.0\.0|\*|\[::\]):5432'"
  check "в pg_hba нет правил для всех"       bash -c "! grep -E '^host.*(0\.0\.0\.0/0|::/0)' $HBA"
  check "ufw: 5432 только с $APP_IP"         bash -c "ufw status | grep -E '5432' | grep -q '$APP_IP'"
  check "роль приложения не суперпользователь" bash -c "[[ \$(runuser -u postgres -- psql -Atc \"SELECT rolsuper FROM pg_roles WHERE rolname='$DB_APP_ROLE'\") == f ]]"
fi

echo
[[ $FAIL -eq 0 ]] && echo "ВСЕ ПРОВЕРКИ ПРОЙДЕНЫ" || { echo "ЕСТЬ НАРУШЕНИЯ"; exit 1; }
