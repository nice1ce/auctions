# Развёртывание Auction System в Linux-среде (Lab 2)

## 1. Архитектура

| Узел | Имя | Внутренний адрес (host-only) | Выход в интернет (NAT) |
|---|---|---|---|
| Сервер приложения | auction-app | 172.16.248.10 | 192.168.81.10 |
| Сервер БД | auction-db | 172.16.248.11 | 192.168.81.11 |

- ОС: Ubuntu Server (Debian-like), без графического интерфейса.
- Приложение: Python 3.12, FastAPI, Uvicorn, запуск как systemd-служба `auctions` (без контейнеров).
- СУБД: PostgreSQL 18 на отдельной машине.
- Внутренняя сеть (host-only) используется для SSH, приложения и обращений приложения к БД. NAT-интерфейс нужен только для установки пакетов.

## 2. Пользователи и роли

| Объект | Назначение |
|---|---|
| `dan` (app), `tim` (db) | администрирование, sudo, вход по SSH-ключу |
| `auctions` (app) | системный пользователь без shell, запускает приложение |
| `auctions_migrator` (БД) | владелец БД, выполняет миграции Alembic |
| `auctions_app` (БД) | рантайм-доступ: SELECT/INSERT/UPDATE/DELETE, без прав на схему |

## 3. Подготовка (вручную, один раз)

1. Создать две ВМ, установить Ubuntu Server (без GUI) и OpenSSH.
2. Настроить статическую адресацию в `/etc/netplan/*.yaml`:
   - NAT-интерфейс: статический адрес, шлюз и DNS;
   - host-only: статический адрес без шлюза и DNS.
3. С рабочей машины: `ssh-copy-id <user>@<внутренний адрес>`.

## 4. Автоматизированное развёртывание

Репозиторий клонируется на обе машины: `git clone https://github.com/nice1ce/auctions ~/auctions && cd ~/auctions/deploy`.

| Шаг | Машина | Команда |
|---|---|---|
| 1 | обе | `sudo ./01-ssh-hardening.sh <admin_user>` |
| 2 | auction-db | `sudo ./02-db.sh` |
| 3 | auction-app | `sudo ./03-app.sh` |
| 4 | auction-app | `./05-migrate.sh`, затем `sudo systemctl restart auctions` |
| 5 | обе | `sudo ./04-firewall.sh app` / `db` |
| 6 | обе | `sudo ./verify.sh app` / `db` |

Пароли ролей БД генерируются на db и сохраняются в `/root/auctions-db-passwords.env` (права 600). Они передаются на app вводом в терминале и в репозиторий не попадают.

## 5. Управление службой

```
sudo systemctl start|stop|restart|status auctions
sudo systemctl enable|disable auctions
journalctl -u auctions -f
```

Автоматический перезапуск: `Restart=always`, `RestartSec=3` в `/etc/systemd/system/auctions.service`.

## 6. Конфигурация отдельно от кода

- Настройки приложения лежат в `/etc/auctions/auctions.env` (владелец `root:auctions`, права `640`), подключаются через `EnvironmentFile`.
- В репозитории только шаблоны: `.env.example`, `deploy/auctions.env.template`, без секретов.

## 7. Требования безопасности (пункт 13)

| № | Требование | Как обеспечено | Как проверить |
|---|---|---|---|
| 1 | Приложение не запускается от root | `User=auctions` в unit-файле, у пользователя нет shell | `ps -o user,pid,cmd -C uvicorn`, `systemctl show auctions -p User` |
| 2 | Лишние порты не открываются | ufw: по умолчанию deny incoming; на app открыты 22 и 8000, на db 22 и 5432 только с app | `sudo ufw status verbose`, `sudo ss -tlnp` |
| 3 | БД доступна только серверу приложения | `listen_addresses` ограничен внутренним адресом, правило в `pg_hba.conf` на `172.16.248.10/32`, правило ufw | `nc -zv 172.16.248.11 5432` со стороннего узла не подключается |
| 4 | Пароли не хранятся в репозитории | секреты в `/etc/auctions/auctions.env` и `/root/auctions-db-passwords.env`; `.env` в `.gitignore` | `deploy/verify.sh`, `git grep`, проверка истории (см. блок проверок) |
| 5 | Вход root по SSH запрещён, пароли отключены | `/etc/ssh/sshd_config.d/00-hardening.conf` | `sudo sshd -T \| grep -E 'permitrootlogin\|passwordauthentication'` |
| 6 | Минимальные права БД | роль приложения без CREATE на схеме и без суперпользователя | `psql ... -c "CREATE TABLE t(x int)"` → permission denied |
| 7 | Код сервиса не изменяется самим сервисом | владелец кода `dan`, группа `auctions` только читает | `sudo -u auctions test -w /opt/auctions/app` |

Отдельные решения: `COOKIE_SECURE=false`, так как стенд работает по HTTP без TLS.

## 8. Проверка на защите

# перезагрузка
sudo reboot
systemctl is-active auctions; curl -s http://172.16.248.10:8000/health      # app
pg_lsclusters                                                                # db

# остановка БД (на db) и диагностика на app
sudo systemctl stop postgresql
journalctl -u auctions -n 30 --no-pager
curl -s -o /dev/null -w '%{http_code}\n' http://127.0.0.1:8000/health
sudo systemctl start postgresql

# процесс, порт, журнал
ps -o user,pid,cmd -C uvicorn
sudo ss -tlnp | grep 8000
journalctl -u auctions -n 50 --no-pager

# изменение параметра службы и восстановление
sudo systemctl edit auctions         # [Service]  RestartSec=10
sudo systemctl daemon-reload && sudo systemctl restart auctions
systemctl show auctions -p RestartUSec
sudo systemctl revert auctions
sudo systemctl daemon-reload && sudo systemctl restart auctions
systemctl show auctions -p RestartUSec

# автоперезапуск после аварии
sudo kill -9 $(systemctl show -p MainPID --value auctions); sleep 5
systemctl status auctions --no-pager
