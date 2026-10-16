PYTHON ?= python3
VENV ?= .venv
BIN := $(VENV)/bin
DATABASE_URL ?= postgresql+psycopg://auction:auction@localhost:5432/auction_db
BACKUP_FILE ?= backup.sql

.PHONY: setup run test quality migrate backup restore verify up down container-check reset-db test-restore sast

setup:
	$(PYTHON) -m venv $(VENV)
	$(BIN)/pip install --upgrade pip
	$(BIN)/pip install -r requirements.txt
	@test -f .env || cp .env.example .env

run:
	$(BIN)/uvicorn app.main:app --reload

# П. 4, 14: Тесты с проверкой покрытия не менее 40%. 
# ЗАПРЕЩЕНО снижать порог --cov-fail-under или добавлять исключения без обоснования в PR.
test:
	$(BIN)/pytest -q --cov=app --cov-report=term-missing --cov-fail-under=40

# П. 7: Статический анализ безопасности (SAST)
sast:
	$(BIN)/bandit -r app/ -ll

quality:
	$(BIN)/ruff check .
	$(BIN)/black --check .

# П. 13: Единая команда verify запускает весь обязательный набор локальных проверок.
# Порядок важен: сначала SAST, потом качество кода, потом тесты с покрытием.
verify: sast quality test

migrate:
	$(BIN)/alembic upgrade head

# П. 9: Проверка создания чистой БД и применения миграций с нуля
reset-db:
	docker compose down -v
	docker compose up -d db
	sleep 5
	docker compose exec -T db psql -U auction -d postgres -c "DROP DATABASE IF EXISTS auction_db;"
	docker compose exec -T db psql -U auction -d postgres -c "CREATE DATABASE auction_db OWNER auction;"
	$(BIN)/alembic upgrade head

backup:
	pg_dump "$(DATABASE_URL)" > "$(BACKUP_FILE)"

restore:
	psql "$(DATABASE_URL)" < "$(BACKUP_FILE)"

# П. 11, 12: Сценарий проверки восстановления после намеренного повреждения данных
test-restore:
	@echo "=== Начало сценария проверки восстановления ==="
	@echo "1. Создаем тестовый лот для эксперимента..."
	@docker compose exec -T db psql -U auction -d auction_db -c "INSERT INTO lots (auction_id, seller_id, name, starting_price, status) SELECT id, 1, 'Backup Test Lot', 100.00, 'AVAILABLE' FROM auctions LIMIT 1;" || echo "Убедитесь, что в БД есть хотя бы один аукцион и продавец с id=1."
	@echo "2. Делаем резервную копию..."
	@$(MAKE) backup
	@echo "3. Намеренно повреждаем данные (удаляем созданный лот)..."
	@docker compose exec -T db psql -U auction -d auction_db -c "DELETE FROM lots WHERE name = 'Backup Test Lot';"
	@echo "4. Восстанавливаем данные из резервной копии..."
	@$(MAKE) restore
	@echo "5. Проверяем целостность данных..."
	@docker compose exec -T db psql -U auction -d auction_db -c "SELECT COUNT(*) as restored_lots_count FROM lots WHERE name = 'Backup Test Lot';"
	@echo "=== Если restored_lots_count = 1, восстановление прошло успешно! ==="

up:
	docker compose up -d db

down:
	docker compose down

container-check:
	docker compose config
	docker compose ps