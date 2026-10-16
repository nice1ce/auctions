# Проверки, миграции и резервное копирование (Lab 3)

## Первоначальная настройка

```bash
make init        # venv + зависимости + .env + PostgreSQL в Docker + миграции
make run         # http://127.0.0.1:8000
```

Версии зависимостей зафиксированы в `requirements.txt` (`==`).

## Что запускает `make verify`

| Шаг | Команда | Зачем |
|---|---|---|
| `policy` | `python scripts/check_policy.py` | Запрет пропуска тестов, снижения порога покрытия и исключений анализаторов без обоснования (п. 14) |
| `lint` | `ruff check .` | Линтер: ошибки, неиспользуемые импорты/переменные, типичные баги (bugbear) |
| `format-check` | `black --check .` | Единое форматирование кода |
| `sast` | `bandit -r app alembic scripts` | Статический анализ безопасности (все уровни серьёзности) |
| `test` | `pytest` | Unit- и интеграционные тесты на отдельной тестовой БД, применение миграций с нуля, проверка покрытия ≥ 85 %, отчёты в `reports/` |

Отчёты после `make test`: `reports/junit.xml` (тесты), `reports/coverage.xml`
и `reports/htmlcov/index.html` (покрытие).

Порядок выбран от быстрых проверок к медленным: если нарушена политика или
стиль, тесты с БД не запускаются.

## Тестовая конфигурация и изоляция

* Тесты используют только `TEST_DATABASE_URL` (по умолчанию `auction_test`)
  и не запустятся, если она совпадает с рабочей `DATABASE_URL`.
* Тестовая БД создаётся автоматически, схема каждый прогон собирается
  с нуля **миграциями Alembic**.
* Каждый тест идёт во внешней транзакции, которая откатывается после теста.

## Покрытие функционала ТЗ тестами

| Сценарий ТЗ | Тесты |
|---|---|
| 1. Регистрация, вход, выход | `test_auth.py`, `test_api_extra.py` (cookie, logout, истечение сессии) |
| 2. Аукцион; продавцы и покупатели | `test_validation.py`, `test_api_extra.py` (даты, длина имени, 404) |
| 3. Лот только для PLANNED/ACTIVE | `test_lifecycle.py`, `test_services.py::test_add_lot_*` |
| 4. Запуск аукциона | `test_services.py::test_start_*` |
| 5. Ставки | `test_services.py::test_*bid*`, `test_lifecycle.py` |
| 6. Отклонение ставки ниже «текущая + 100 ₽» | `test_services.py` (199.99 / 200.00 / 599.99 / 600.00), `test_business_rule.py` |
| 7. Продажа закрывает лот | `test_lifecycle.py`, `test_services.py::test_sale_*` |
| 8. Продажи и выручка | `test_api_extra.py::test_revenue_is_sum_of_sales` |
| 9. Завершение/отмена → UNSOLD | `test_services.py::test_closing_*`, `test_lifecycle.py` |
| Lab 3: счётчик просмотров | `test_api_extra.py::test_lot_views_*`, `test_services.py::test_increment_*`, `test_migrations.py` |

Покрыты все 9 сценариев и все бизнес-правила раздела 6 ТЗ.

## Мутационное тестирование

`make mutation` по очереди вносит в `app/services.py` и `app/auth.py` мутации
(`<`↔`<=`, `==`↔`!=`, `not in`→`in`, смена статуса, числа, шага ставки) и
запускает тесты. Каждый мутант должен «убиваться» хотя бы одним тестом.

## Миграции

Цепочка: `0001_initial` → `0002_indexes` → `0003_constraints` →
`0004_users_and_sessions` → `0005_lot_views_count` (новая функция Lab 3).

* Чистая БД: `make db-reset` (пересоздать рабочую БД и применить все миграции);
  в тестах — `test_migrations.py::test_clean_database_upgrades_to_head`.
* БД с данными: `make migrate-check` (upgrade head + `alembic check`: схема
  совпадает с моделями); в тестах —
  `test_upgrade_of_database_with_existing_data` (данные на ревизии 0004
  переживают обновление, `views_count = 0`).

## Резервное копирование

```bash
make backup          # pg_dump --clean --if-exists -> backups/backup.sql
make restore         # восстановление одной транзакцией
make backup-check    # копия -> порча данных -> восстановление -> сверка отпечатка
```

По умолчанию `pg_dump`/`psql` запускаются внутри контейнера `db`. Для
локального PostgreSQL: `make backup PG_EXEC=`.
