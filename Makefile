PYTHON ?= python3
VENV ?= .venv
BIN := $(VENV)/bin
DATABASE_URL ?= postgresql+psycopg://auction:auction@localhost:5432/auction_db
BACKUP_FILE ?= backup.sql

.PHONY: setup run test quality migrate backup restore verify up down container-check

setup:
	$(PYTHON) -m venv $(VENV)
	$(BIN)/pip install --upgrade pip
	$(BIN)/pip install -r requirements.txt
	@test -f .env || cp .env.example .env

run:
	$(BIN)/uvicorn app.main:app --reload

test:
	$(BIN)/pytest -q

quality:
	$(BIN)/ruff check .
	$(BIN)/black --check .

migrate:
	$(BIN)/alembic upgrade head

backup:
	pg_dump "$(DATABASE_URL)" > "$(BACKUP_FILE)"

restore:
	psql "$(DATABASE_URL)" < "$(BACKUP_FILE)"

verify: quality test

up:
	docker compose up -d db

down:
	docker compose down

container-check:
	docker compose config
	docker compose ps
