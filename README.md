# Auction System

Приложение системы аукционов для учета лотов, продавцов, покупателей, ставок, продаж и выручки.

Первая версия реализует только функциональность: HTTP API, PostgreSQL, Alembic, простую HTML/CSS/JS веб-часть, тесты, Makefile, документацию и базовый CI.

## Стек

Python 3.12, FastAPI, SQLAlchemy 2, PostgreSQL, Alembic, Pydantic Settings, pytest, Ruff, Black, HTML/CSS/JS.

## Быстрый старт

В контейнерах (Lab 4, ВМ Linux с Docker):

```bash
cp .env.example .env && make env-password
make container-up   # container-check -> сборка -> nginx + 2 экземпляра + PostgreSQL
```

Откройте `http://127.0.0.1:8080`. Подробности: `docs/CONTAINERS.md`.

Разработка на хосте:

```bash
make init   # venv, зависимости, .env, PostgreSQL в Docker (порт на 127.0.0.1), миграции
make run
```

Откройте `http://127.0.0.1:8000`.

## Команды

`make init` — единый сценарий первоначальной настройки  
`make setup` — окружение и зафиксированные зависимости  
`make run` — FastAPI  
`make up` / `make down` — локальный PostgreSQL  
`make migrate` — Alembic upgrade head  
`make migrate-check` — обновление БД с данными + сверка схемы с моделями  
`make db-reset` — пересоздать чистую БД и применить миграции  
`make verify` — policy + ruff + black + bandit + тесты с покрытием  
`make mutation` — мутационное тестирование бизнес-логики  
`make backup` / `make restore` — резервная копия и восстановление  
`make backup-check` — копия → порча данных → восстановление → сверка  

Контейнерное окружение (Lab 4):

`make container-check` — автоматическая проверка Dockerfile, Compose, образа и стенда  
`make container-up` — применить изменения окружения (только после container-check)  
`make container-down` / `make container-ps` / `make container-logs` / `make container-users`  
`make container-migrate` — миграции Alembic в контейнере  
`make container-backup` / `make container-restore` — резервная копия и восстановление в контейнере  
`make container-persistence-check` — данные после пересоздания и обновления образа  
`make container-stop-check` — корректное завершение по SIGTERM  
`make container-restore-check` — восстановление БД в новый volume  
`make container-lb-check` — балансировка, отказ узла, ограничение частоты  
`make lock` / `make pin-digest` / `make env-password` — lock-файл, digest образов, пароль БД

CI и безопасность (Lab 5):

`make ci` — все обязательные проверки pipeline локально  
`make deps-audit` / `make secrets-scan` / `make image-scan` — зависимости, секреты, образ  
`make migrate-roundtrip` — миграции вниз до base и обратно  
`make registry-up` / `make image-publish` — локальный Docker Registry и публикация образа  
`make ci-guard` — страж критических файлов относительно `origin/main`  
`make ci-demo DEMO=good|defect|delete-test|...` — демонстрационные PR

Подробности о проверках, миграциях и бэкапах: `docs/TESTING.md`, о контейнерах: `docs/CONTAINERS.md`, о CI: `docs/CI.md`.

## API

Swagger: `/docs`  
ReDoc: `/redoc`  
Health: `/health` (liveness), `/health/ready` (readiness: доступна ли БД)  
Version: `/version`  
Каждый ответ содержит заголовок `X-Instance-Id` — идентификатор экземпляра приложения.

Подробности: `docs/API.md`.

## Бизнес-правила

1. Лот можно добавить, изменить или удалить только пока его аукцион в статусе `PLANNED` или `ACTIVE`. После `FINISHED`/`CANCELLED` лоты этого аукциона неизменны.
2. Ставка принимается только для лота `AVAILABLE` в аукционе со статусом `ACTIVE`, и должна быть не меньше текущей цены (максимальной ставки, либо стартовой цены, если ставок ещё нет) плюс минимальный шаг **100 ₽**.
3. Продажа создаётся явно (оператор указывает покупателя и цену) и всегда привязана к конкретному лоту: `POST /api/sales` возможен только для лота `AVAILABLE` в `ACTIVE` аукционе, цена не может быть ниже стартовой. Создание продажи сразу закрывает лот (`SOLD`), продать лот повторно нельзя.
4. При завершении (`finish`) или отмене (`cancel`) аукциона все ещё не проданные лоты (`AVAILABLE`) автоматически переводятся в `UNSOLD`.
5. Аукцион нельзя удалить, если у него уже есть лоты; лот нельзя удалить, если на него уже сделаны ставки.
6. Выручка рассчитывается как сумма цен продаж и не хранится отдельной сущностью.
7. `GET /api/lots` и `GET /api/lots/{id}` дополнительно отдают вычисляемое поле `current_price`: цена продажи (если лот продан), иначе максимальная ставка, иначе стартовая цена — чтобы в интерфейсе всегда была видна актуальная цена лота, а не только стартовая.
8. `POST /api/lots/{id}/view` увеличивает счётчик просмотров лота `views_count` (Lab 3, миграция `0005_lot_views_count`).

## Аутентификация

Базовая, без ролей: `POST /api/auth/register` (email + пароль, от 8 символов), `POST /api/auth/login`, `POST /api/auth/logout`, `GET /api/auth/me`. Сессия — серверная, в httponly cookie (без JWT и без ручного управления токеном на фронте). Пароли хранятся как bcrypt-хеш.

Это самостоятельная функция, а не контроль доступа: вход в систему пока ничего не блокирует и не открывает — все остальные эндпоинты (аукционы, лоты, ставки, продавцы/покупатели, продажи, статистика) как были доступны без входа, так и остаются. Разделение прав между пользователями сознательно не реализовано в этой версии.

## Git

Каждая функциональность: issue → `feature/...` → несколько осмысленных коммитов → `make verify` → PR → review → merge. Первая принятая версия помечается `v0.1.0`.
