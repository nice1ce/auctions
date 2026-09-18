# Модель данных

Сущности: Auction, Seller, Buyer, Lot, Bid, Sale.

```text
Auction 1 ─── N Lot
Seller  1 ─── N Lot
Lot     1 ─── N Bid
Buyer   1 ─── N Bid
Lot     1 ─── 0..1 Sale
Buyer   1 ─── N Sale
```

Revenue не является отдельной таблицей: `SUM(sales.price)`.

Ограничения БД:
- `end_at > start_at`;
- положительные цены/ставки;
- внешний ключ для связей;
- `sales.lot_id` уникален.

Жизненный цикл статусов (проверяется в сервисном слое `app/services.py`, а не в БД):

```text
Auction: PLANNED ──start──> ACTIVE ──finish──> FINISHED
                       └───────cancel──────> CANCELLED

Lot:     AVAILABLE ──create_sale──> SOLD
                └───auction.finish/cancel──> UNSOLD
```

- Лот можно создавать/редактировать/удалять только пока `auction.status` в `{PLANNED, ACTIVE}`.
- При переходе аукциона в `FINISHED` или `CANCELLED` все его лоты в статусе `AVAILABLE` массово переводятся в `UNSOLD`.
- Продажа (`Sale`) создаётся только для лота `AVAILABLE` активного аукциона и атомарно переводит лот в `SOLD`; повторная продажа невозможна благодаря уникальности `sales.lot_id` и проверке статуса лота.
- Прикладные правила превосходства ставок, стартовой цены продажи и переходов статусов находятся в сервисном слое.
