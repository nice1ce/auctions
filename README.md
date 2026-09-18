# Auction System

Учебное приложение для учета аукционов, лотов, продавцов, покупателей, ставок, продаж и выручки.

Первая версия реализует только функциональность Lab 1: HTTP API, PostgreSQL, Alembic, простую HTML/CSS/JS веб-часть, тесты, Makefile, документацию и базовый CI. Архитектура оставляет место для последующих лабораторных без раннего добавления их функциональности.

## Стек

Python 3.12, FastAPI, SQLAlchemy 2, PostgreSQL, Alembic, Pydantic Settings, pytest, Ruff, Black, HTML/CSS/JS.

## Быстрый старт

```bash
cp .env.example .env
make setup
make migrate
make run
```

Откройте `http://127.0.0.1:8000`.

PostgreSQL можно удобно поднять локально:

```bash
make up
make migrate
make run
```

## Команды

`make setup` — окружение и зависимости  
`make run` — FastAPI  
`make test` — тесты  
`make quality` — Ruff + Black  
`make migrate` — Alembic upgrade head  
`make backup` — pg_dump  
`make restore` — восстановление из backup.sql  
`make verify` — quality + tests  
`make up` / `make down` — локальный PostgreSQL  
`make container-check` — базовая проверка Compose

## API

Swagger: `/docs`  
ReDoc: `/redoc`  
Health: `/health`  
Version: `/version`

Подробности: `docs/API.md`.

## Бизнес-правила

1. Лот можно добавить, изменить или удалить только пока его аукцион в статусе `PLANNED` или `ACTIVE`. После `FINISHED`/`CANCELLED` лоты этого аукциона неизменны.
2. Ставка принимается только для лота `AVAILABLE` в аукционе со статусом `ACTIVE`, и должна быть строго больше текущей максимальной (или стартовой цены, если ставок ещё нет).
3. Продажа создаётся явно (оператор указывает покупателя и цену) и всегда привязана к конкретному лоту: `POST /api/sales` возможен только для лота `AVAILABLE` в `ACTIVE` аукционе, цена не может быть ниже стартовой. Создание продажи сразу закрывает лот (`SOLD`), продать лот повторно нельзя.
4. При завершении (`finish`) или отмене (`cancel`) аукциона все ещё не проданные лоты (`AVAILABLE`) автоматически переводятся в `UNSOLD`.
5. Аукцион нельзя удалить, если у него уже есть лоты; лот нельзя удалить, если на него уже сделаны ставки.
6. Выручка рассчитывается как сумма цен продаж и не хранится отдельной сущностью.

## Git

Каждая функциональность: issue → `feature/...` → несколько осмысленных коммитов → `make verify` → PR → review → merge. Первая принятая версия помечается `v0.1.0`.
