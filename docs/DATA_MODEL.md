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

Прикладное правило превосходства ставок находится в сервисном слое.
