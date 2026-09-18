# Auction System

Приложение для учета аукционов, лотов, продавцов, покупателей, ставок, продаж и выручки.

Первая версия реализует только функциональность: HTTP API, PostgreSQL, Alembic, простую HTML/CSS/JS веб-часть, тесты, Makefile, документацию и базовый CI. Архитектура оставляет место для последующих лабораторных без раннего добавления их функциональности.

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

1. Ставка принимается только для лота активного аукциона.
2. Новая ставка должна быть строго больше текущей максимальной.
3. Лот нельзя продать повторно.
4. Цена продажи равна победившей ставке.
5. Выручка рассчитывается как сумма продаж и не хранится отдельной сущностью.

## Git

Каждая функциональность: issue → `feature/...` → несколько осмысленных коммитов → `make verify` → PR → review → merge. Первая принятая версия помечается `v0.1.0`.
