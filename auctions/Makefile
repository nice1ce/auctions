# Auction System — команды разработки (Lab 3).
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

.PHONY: help setup init up down db-wait run migrate migrate-check db-reset \
	policy lint format format-check sast test verify mutation \
	backup restore backup-check container-check clean

help:
	@grep -E '^[a-z-]+:.*## ' $(MAKEFILE_LIST) | sed 's/:.*## /\t/'

# ---- Установка и запуск -----------------------------------------------------

setup: ## venv + зафиксированные зависимости + .env
	$(PYTHON) -m venv $(VENV)
	$(BIN)/pip install --upgrade pip
	$(BIN)/pip install -r requirements.txt
	@test -f .env || cp .env.example .env

init: setup up db-wait migrate ## единый сценарий первоначальной настройки
	@echo "Готово: make run -> http://127.0.0.1:8000"

up: ## поднять PostgreSQL в Docker
	docker compose up -d db

down:
	docker compose down

db-wait:
	@for i in $$(seq 1 30); do \
		$(PG_EXEC) pg_isready -q -d "$(PG_URL)" && exit 0; sleep 1; \
	done; echo "PostgreSQL недоступен"; exit 1

run: ## запустить приложение
	$(BIN)/uvicorn app.main:app --reload

# ---- Миграции (п. 8, 9) -----------------------------------------------------

migrate: ## применить миграции к рабочей БД
	$(BIN)/alembic upgrade head

migrate-check: ## обновить БД с данными до head и сверить схему с моделями
	$(BIN)/alembic current
	$(BIN)/alembic upgrade head
	$(BIN)/alembic check

db-reset: ## пересоздать ЧИСТУЮ рабочую БД и применить все миграции
	$(PG_EXEC) dropdb --if-exists --force --maintenance-db="$(PG_MAINTENANCE_URL)" $(DB_NAME)
	$(PG_EXEC) createdb --maintenance-db="$(PG_MAINTENANCE_URL)" $(DB_NAME)
	$(BIN)/alembic upgrade head

# ---- Проверки (п. 7, 13, 14) ------------------------------------------------

policy: ## запрет пропуска тестов, снижения порогов и исключений без обоснования
	$(BIN)/python scripts/check_policy.py

lint: ## линтер
	$(BIN)/ruff check .

format-check: ## проверка форматирования
	$(BIN)/black --check .

format: ## автоформатирование
	$(BIN)/black .
	$(BIN)/ruff check --fix .

sast: ## статический анализ безопасности
	$(BIN)/bandit -r app alembic scripts

test: ## unit + интеграционные тесты на тестовой БД, отчёты в reports/
	$(BIN)/pytest

verify: policy lint format-check sast test ## весь обязательный набор проверок

mutation: ## мутационное тестирование бизнес-логики (несколько минут)
	$(BIN)/python scripts/mutation_check.py

# ---- Резервное копирование (п. 11, 12) ----------------------------------------

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
	scripts/backup_restore_check.sh

# ---- Прочее -------------------------------------------------------------------

container-check:
	docker compose config
	docker compose ps

clean:
	rm -rf reports .pytest_cache .ruff_cache .coverage
