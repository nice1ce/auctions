# Auction System — команды разработки (Lab 3), контейнеров (Lab 4) и CI (Lab 5).
# CI (.github/workflows/ci.yml) вызывает эти же цели — локально и в CI одни команды.
# Переменные берутся из .env (создаётся из .env.example командой make setup).
-include .env
export

PYTHON ?= python3
VENV ?= .venv
BIN := $(VENV)/bin

# pg_dump/psql понимают только postgresql://, без драйвера «+psycopg».
PG_URL = $(subst +psycopg,,$(DATABASE_URL))
DB_NAME = $(lastword $(subst /, ,$(PG_URL)))
PG_MAINTENANCE_URL = $(patsubst %/$(DB_NAME),%/postgres,$(PG_URL))
# По умолчанию клиенты PostgreSQL запускаются внутри контейнера db, ставить
# их на хост не нужно. С локальным PostgreSQL: make backup PG_EXEC=
PG_EXEC ?= docker compose exec -T db
BACKUP_FILE ?= backups/backup.sql

# Lab 4
COMPOSE ?= docker compose
# Для разработки на хосте: тот же compose + публикация 5432 только на 127.0.0.1.
COMPOSE_DEV = $(COMPOSE) -f docker-compose.yml -f docker-compose.dev.yml
CONTAINER_CHECK = $(PYTHON) scripts/container_check.py $(CONTAINER_CHECK_FLAGS)
# В CI образ собирается отдельной стадией: CONTAINER_CHECK_FLAGS=--no-build
CONTAINER_CHECK_FLAGS ?=
CONTAINER_BACKUP ?= backups/container-backup.sql
# Базовый образ для make lock — тот же, что в Dockerfile.
PYTHON_IMAGE = $(shell awk '$$1 == "FROM" { print $$2; exit }' Dockerfile)

# Lab 5: инструменты безопасности (версии зафиксированы) и публикация образа
GITLEAKS_IMAGE = ghcr.io/gitleaks/gitleaks:v8.21.2
IMAGE ?= auctions-app:$(APP_VERSION)
REGISTRY ?= localhost:5000
GUARD_BASE ?= origin/main

.PHONY: help setup init up down db-wait run migrate migrate-check db-reset \
	policy lint format format-check sast test verify mutation \
	backup restore backup-check clean \
	container-check container-up container-down container-ps container-logs \
	container-users container-migrate container-backup container-restore \
	container-persistence-check container-stop-check container-restore-check \
	container-lb-check container-all-checks lock pin-digest env-password \
	db-password-apply migrate-roundtrip deps-audit secrets-scan image-scan \
	registry-up registry-down image-publish ci ci-guard ci-demo

help:
	@grep -hE '^[a-z-]+:.*## ' Makefile | sed 's/:.*## /\t/'

# ---- Установка и запуск (разработка на хосте) ----------------------------------

setup: ## venv + зафиксированные зависимости + .env
	$(PYTHON) -m venv $(VENV)
	$(BIN)/pip install --upgrade pip
	$(BIN)/pip install -r requirements.txt
	@test -f .env || cp .env.example .env

init: setup up db-wait migrate ## единый сценарий первоначальной настройки
	@echo "Готово: make run -> http://127.0.0.1:8000"

up: ## поднять PostgreSQL для разработки (порт только на 127.0.0.1)
	$(COMPOSE_DEV) up -d db

down:
	$(COMPOSE) down

db-wait:
	@for i in $$(seq 1 30); do \
		$(PG_EXEC) pg_isready -q -d "$(PG_URL)" && exit 0; sleep 1; \
	done; echo "PostgreSQL недоступен"; exit 1

run: ## запустить приложение на хосте
	$(BIN)/uvicorn app.main:app --reload

# ---- Миграции (Lab 3, п. 8, 9) ---------------------------------------------------

migrate: ## применить миграции к рабочей БД
	$(BIN)/alembic upgrade head

migrate-check: ## обновить БД с данными до head и сверить схему с моделями
	$(BIN)/alembic current
	$(BIN)/alembic upgrade head
	$(BIN)/alembic check

migrate-roundtrip: ## Lab 5: все миграции вниз до base и снова до head + сверка схемы
	$(BIN)/alembic upgrade head
	$(BIN)/alembic downgrade base
	$(BIN)/alembic upgrade head
	$(BIN)/alembic check

db-reset: ## пересоздать ЧИСТУЮ рабочую БД и применить все миграции
	$(PG_EXEC) dropdb --if-exists --force --maintenance-db="$(PG_MAINTENANCE_URL)" $(DB_NAME)
	$(PG_EXEC) createdb --maintenance-db="$(PG_MAINTENANCE_URL)" $(DB_NAME)
	$(BIN)/alembic upgrade head

# ---- Проверки (Lab 3, п. 7, 13, 14) ----------------------------------------------

policy: ## запрет пропуска тестов, снижения порогов и исключений без обоснования
	$(BIN)/python scripts/check_policy.py

lint: ## линтер (отчёт: reports/ruff.xml)
	@mkdir -p reports
	$(BIN)/ruff check --exit-zero --output-format junit --output-file reports/ruff.xml .
	$(BIN)/ruff check .

format-check: ## проверка форматирования (отчёт: reports/black.diff)
	@mkdir -p reports
	$(BIN)/black --check --diff . > reports/black.diff 2>&1 || { cat reports/black.diff; exit 1; }

format: ## автоформатирование
	$(BIN)/black .
	$(BIN)/ruff check --fix .

sast: ## статический анализ безопасности (отчёт: reports/bandit.json)
	@mkdir -p reports
	$(BIN)/bandit -q -r app alembic scripts -f json -o reports/bandit.json || { $(BIN)/bandit -r app alembic scripts; exit 1; }

test: ## unit + интеграционные тесты на тестовой БД, отчёты в reports/
	$(BIN)/pytest

verify: policy lint format-check sast test ## весь обязательный набор проверок

mutation: ## мутационное тестирование бизнес-логики (несколько минут)
	$(BIN)/python scripts/mutation_check.py

# ---- Резервное копирование (Lab 3, п. 11, 12) ------------------------------------

backup: ## резервная копия рабочей БД в $(BACKUP_FILE)
	@mkdir -p "$(dir $(BACKUP_FILE))"
	$(PG_EXEC) pg_dump --clean --if-exists --no-owner --no-privileges "$(PG_URL)" > "$(BACKUP_FILE).tmp"
	@mv "$(BACKUP_FILE).tmp" "$(BACKUP_FILE)"
	@echo "Резервная копия: $(BACKUP_FILE)"

restore: ## восстановить рабочую БД из $(BACKUP_FILE) (одной транзакцией)
	@test -s "$(BACKUP_FILE)" || { echo "Нет файла $(BACKUP_FILE)"; exit 1; }
	$(PG_EXEC) psql -q -X -v ON_ERROR_STOP=1 --single-transaction "$(PG_URL)" < "$(BACKUP_FILE)" > /dev/null
	@echo "Восстановлено из $(BACKUP_FILE)"

backup-check: ## сценарий: копия -> порча данных -> восстановление -> сверка
	bash scripts/backup_restore_check.sh

# ---- Контейнерное окружение (Lab 4) ----------------------------------------------
# Правило п. 14: окружение изменяется ТОЛЬКО через make container-up, который
# сначала выполняет container-check и не применяет изменения при нарушениях.

container-check: ## п. 12: проверка Dockerfile, Compose, образа и запущенного стенда
	$(CONTAINER_CHECK)

container-up: ## п. 14: container-check -> docker compose up -> проверка стенда
	$(CONTAINER_CHECK) --skip-runtime
	$(COMPOSE) up -d --remove-orphans
	$(CONTAINER_CHECK) --runtime-only --wait 180
	@echo "Стенд: http://127.0.0.1:$${HTTP_PORT:-8080}"

container-down: ## остановить стенд (контейнеры удаляются, volume с БД остаётся)
	$(COMPOSE) down

container-ps: ## состояние контейнеров
	$(COMPOSE) ps --all

container-logs: ## журналы всех контейнеров
	$(COMPOSE) logs --tail=100

container-users: ## от какого пользователя работают процессы в контейнерах
	@for s in db app1 app2 nginx; do \
		printf '%-6s %s\n' "$$s" "$$($(COMPOSE) exec -T $$s id)"; \
	done
	@for s in db app1 app2 nginx; do \
		echo "--- $$s (uid процессов)"; \
		docker top "$$($(COMPOSE) ps -q $$s)" -eo uid,pid,comm; \
	done

container-migrate: ## п. 10: миграции Alembic в контейнере (upgrade head)
	$(COMPOSE) run --rm migrate

container-backup: ## п. 10: pg_dump внутри контейнера db -> $(CONTAINER_BACKUP)
	bash scripts/container_db.sh backup "$(CONTAINER_BACKUP)"

container-restore: ## п. 10: восстановить БД в контейнере из $(CONTAINER_BACKUP)
	bash scripts/container_db.sh restore "$(CONTAINER_BACKUP)"

container-persistence-check: ## п. 9: данные после пересоздания и обновления образа
	bash scripts/container_persistence_check.sh

container-stop-check: ## п. 5: корректное завершение по SIGTERM (exit 0)
	bash scripts/container_stop_check.sh app1

container-restore-check: ## п. 10: восстановление БД в НОВЫЙ volume
	bash scripts/container_restore_check.sh

container-lb-check: ## доп.: балансировка, отказ узла, ограничение частоты
	bash scripts/container_lb_check.sh

container-all-checks: container-up container-stop-check container-lb-check container-persistence-check ## все сценарии, кроме восстановления в новый volume

lock: ## пересобрать requirements.lock в базовом образе из Dockerfile
	docker run --rm --user "$$(id -u):$$(id -g)" -e HOME=/tmp -v "$(CURDIR)":/src -w /src \
		$(PYTHON_IMAGE) sh -c '\
		python -m venv /tmp/venv && \
		/tmp/venv/bin/pip install -q --disable-pip-version-check --only-binary=:all: -r requirements-runtime.txt && \
		{ sed -n "1,3p" requirements.lock; /tmp/venv/bin/pip freeze; } > /tmp/requirements.lock && \
		cp /tmp/requirements.lock requirements.lock'
	@echo "requirements.lock обновлён"

pin-digest: ## показать digest используемых образов для фиксации (image@sha256:...)
	@for image in $$($(COMPOSE) config --images | grep -v '^auctions-app:') $(PYTHON_IMAGE); do \
		docker pull -q "$$image" > /dev/null && \
		docker image inspect --format '{{index .RepoDigests 0}}' "$$image"; \
	done

env-password: ## сгенерировать стойкий пароль БД в .env
	$(PYTHON) scripts/set_db_password.py

db-password-apply: ## применить пароль из .env к уже инициализированной БД
	@printf "ALTER USER \"%s\" PASSWORD '%s';\n" "$$POSTGRES_USER" "$$POSTGRES_PASSWORD" \
		| $(COMPOSE) exec -T db psql -X -q -U "$$POSTGRES_USER" -d postgres
	@echo "Пароль в БД обновлён. Пересоздайте контейнеры: make container-up"

# ---- CI и безопасность (Lab 5) -----------------------------------------------------

deps-audit: ## п. 12: уязвимости зависимостей образа и окружения (pip-audit)
	$(PYTHON) scripts/vuln_gate.py deps --python $(BIN)/python

secrets-scan: ## п. 12: поиск секретов во всей истории git (gitleaks)
	@mkdir -p reports
	docker run --rm --user "$$(id -u):$$(id -g)" -e HOME=/tmp -v "$(CURDIR)":/repo $(GITLEAKS_IMAGE) \
		git --no-banner --redact --config /repo/.gitleaks.toml \
		--report-format sarif --report-path /repo/reports/gitleaks.sarif /repo

image-scan: ## п. 12: анализ образа $(IMAGE) (Trivy): CRITICAL с исправлением — провал
	$(PYTHON) scripts/vuln_gate.py image "$(IMAGE)"

registry-up: ## локальный Docker Registry с паролем на $(REGISTRY)
	bash scripts/local_registry.sh up

registry-down: ## остановить локальный Docker Registry (данные остаются в volume)
	bash scripts/local_registry.sh down

image-publish: ## п. 9: опубликовать $(IMAGE) в $(REGISTRY) с тегами версии и commit SHA
	bash scripts/local_registry.sh publish "$(IMAGE)"

ci: verify migrate-check migrate-roundtrip backup-check deps-audit secrets-scan container-check ## все обязательные проверки pipeline локально

ci-guard: ## п. 15: страж критических файлов — сравнение с $(GUARD_BASE)
	$(PYTHON) scripts/ci_guard.py --base "$(GUARD_BASE)" --head HEAD

ci-demo: ## п. 15–16: демонстрационная ветка, DEMO=good|defect|delete-test|skip-test|lower-coverage|disable-check|weaken-lint
	bash scripts/ci_demo.sh "$(DEMO)"

# ---- Прочее ------------------------------------------------------------------------

clean:
	rm -rf reports .pytest_cache .ruff_cache .coverage
