#!/usr/bin/env bash
set -euo pipefail
source "$(dirname "$0")/config.sh"
[[ $EUID -eq 0 ]] || { echo "Запускайте через sudo"; exit 1; }

apt-get update -qq
apt-get install -y postgresql openssl

PGV=$(ls /etc/postgresql | sort -V | tail -1)
PGCONF=/etc/postgresql/$PGV/main

# --- пароли: из окружения, из ранее сохранённого файла или новые ---
CRED=/root/auctions-db-passwords.env
if [[ -f $CRED ]]; then source "$CRED"; fi
DB_APP_PASSWORD=${DB_APP_PASSWORD:-$(openssl rand -hex 24)}
DB_MIGRATOR_PASSWORD=${DB_MIGRATOR_PASSWORD:-$(openssl rand -hex 24)}
( umask 077
  printf 'DB_APP_PASSWORD=%s\nDB_MIGRATOR_PASSWORD=%s\n' \
    "$DB_APP_PASSWORD" "$DB_MIGRATOR_PASSWORD" > "$CRED" )
export DB_NAME DB_APP_ROLE DB_MIGRATOR_ROLE DB_APP_PASSWORD DB_MIGRATOR_PASSWORD

# --- слушаем только localhost и внутренний адрес ---
install -d "$PGCONF/conf.d"
echo "listen_addresses = 'localhost,$DB_IP'" > "$PGCONF/conf.d/10-auctions.conf"

# --- pg_hba: только сервер приложения, только по паролю ---
add_hba() { grep -qxF "$1" "$PGCONF/pg_hba.conf" || echo "$1" >> "$PGCONF/pg_hba.conf"; }
add_hba "host  $DB_NAME  $DB_APP_ROLE  $APP_IP/32  scram-sha-256"
add_hba "host  $DB_NAME  $DB_MIGRATOR_ROLE  $APP_IP/32  scram-sha-256"

systemctl restart postgresql

# --- роли и база; пароли передаются через окружение (\getenv), не через аргументы ---
runuser -u postgres -- psql -v ON_ERROR_STOP=1 <<'SQL'
\getenv db_name DB_NAME
\getenv app_role DB_APP_ROLE
\getenv mig_role DB_MIGRATOR_ROLE
\getenv app_pw DB_APP_PASSWORD
\getenv mig_pw DB_MIGRATOR_PASSWORD

SELECT format('CREATE ROLE %I LOGIN', :'mig_role')
  WHERE NOT EXISTS (SELECT FROM pg_roles WHERE rolname = :'mig_role') \gexec
SELECT format('CREATE ROLE %I LOGIN', :'app_role')
  WHERE NOT EXISTS (SELECT FROM pg_roles WHERE rolname = :'app_role') \gexec
ALTER ROLE :"mig_role" PASSWORD :'mig_pw';
ALTER ROLE :"app_role" PASSWORD :'app_pw';

SELECT format('CREATE DATABASE %I OWNER %I', :'db_name', :'mig_role')
  WHERE NOT EXISTS (SELECT FROM pg_database WHERE datname = :'db_name') \gexec
REVOKE ALL ON DATABASE :"db_name" FROM PUBLIC;
GRANT CONNECT ON DATABASE :"db_name" TO :"app_role";

\c :db_name
GRANT USAGE ON SCHEMA public TO :"app_role";
ALTER DEFAULT PRIVILEGES FOR ROLE :"mig_role" IN SCHEMA public
  GRANT SELECT, INSERT, UPDATE, DELETE ON TABLES TO :"app_role";
ALTER DEFAULT PRIVILEGES FOR ROLE :"mig_role" IN SCHEMA public
  GRANT USAGE, SELECT ON SEQUENCES TO :"app_role";
-- для повторного запуска, когда таблицы уже есть
GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA public TO :"app_role";
GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA public TO :"app_role";
SQL

echo
echo "Готово. Пароли сохранены в $CRED (только root). В репозиторий не добавлять."
ss -tlnp | grep 5432
