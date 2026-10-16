#!/usr/bin/env bash
# Lab 3, п. 11–12: резервная копия -> намеренная порча данных -> восстановление
# -> сверка. Запускается через `make backup-check` (переменные приходят из
# Makefile/.env). Завершается с ошибкой, если данные не совпали с исходными.
set -euo pipefail

: "${PG_URL:?PG_URL не задан — запускайте через make backup-check}"
PG_EXEC=${PG_EXEC-docker compose exec -T db}
MAKE=${MAKE:-make}

sql() { $PG_EXEC psql -X -q -t -A -v ON_ERROR_STOP=1 "$PG_URL" -c "$1"; }

# Отпечаток всех бизнес-данных: md5 от всех строк всех таблиц.
fingerprint() {
  sql "SELECT md5(string_agg(row_text, '|' ORDER BY row_text)) FROM (
         SELECT 'auction:' || a::text AS row_text FROM auctions a
         UNION ALL SELECT 'seller:' || s::text FROM sellers s
         UNION ALL SELECT 'buyer:'  || b::text FROM buyers b
         UNION ALL SELECT 'lot:'    || l::text FROM lots l
         UNION ALL SELECT 'bid:'    || d::text FROM bids d
         UNION ALL SELECT 'sale:'   || x::text FROM sales x
       ) t"
}

counts() {
  sql "SELECT format('лотов: %s, ставок: %s, продаж: %s, «испорченных» лотов: %s',
         (SELECT count(*) FROM lots), (SELECT count(*) FROM bids),
         (SELECT count(*) FROM sales),
         (SELECT count(*) FROM lots WHERE name = 'ИСПОРЧЕНО'))"
}

echo "== 0. Подготовка: если БД пустая, добавляем демонстрационные данные"
if [[ $(sql "SELECT count(*) FROM lots") == 0 ]]; then
  sql "WITH a AS (INSERT INTO auctions (name, start_at, end_at, status)
                  VALUES ('Демо-аукцион', now(), now() + interval '1 day', 'ACTIVE')
                  RETURNING id),
            s AS (INSERT INTO sellers (name, email) VALUES ('Демо-продавец', 's@demo')
                  RETURNING id),
            b AS (INSERT INTO buyers (name, email) VALUES ('Демо-покупатель', 'b@demo')
                  RETURNING id),
            l AS (INSERT INTO lots (auction_id, seller_id, name, starting_price)
                  SELECT a.id, s.id, 'Демо-лот', 100 FROM a, s RETURNING id)
       INSERT INTO bids (lot_id, buyer_id, amount) SELECT l.id, b.id, 200 FROM l, b" >/dev/null
fi
BEFORE=$(fingerprint)
echo "   $(counts)"
echo "   отпечаток данных: $BEFORE"

echo "== 1. Создаём резервную копию"
$MAKE -s backup

echo "== 2. Намеренно портим данные: удаляем продажи и ставки, затираем лоты"
sql "DELETE FROM sales; DELETE FROM bids;
     UPDATE lots SET name = 'ИСПОРЧЕНО', starting_price = 0.01"
DAMAGED=$(fingerprint)
echo "   $(counts)"
echo "   отпечаток данных: $DAMAGED"
if [[ "$DAMAGED" == "$BEFORE" ]]; then
  echo "Порча данных не изменила отпечаток — проверка некорректна"; exit 1
fi

echo "== 3. Восстанавливаем из резервной копии"
$MAKE -s restore

AFTER=$(fingerprint)
echo "   $(counts)"
echo "   отпечаток данных: $AFTER"
if [[ "$AFTER" == "$BEFORE" ]]; then
  echo "== OK: данные восстановлены полностью (отпечатки совпадают)"
else
  echo "== ОШИБКА: данные после восстановления отличаются от исходных"; exit 1
fi
