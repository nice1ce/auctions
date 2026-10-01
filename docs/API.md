# HTTP API

Service: `GET /health`, `GET /version`

Auth: `POST /api/auth/register` (тело: `email`, `password` от 8 символов), `POST /api/auth/login`, `POST /api/auth/logout`, `GET /api/auth/me`. Сессия — httponly cookie `session_token`. Без ролей: вход не влияет на доступ к остальным эндпоинтам ниже — они как были открыты без авторизации, так и остаются.

Auctions: `GET/POST /api/auctions`, `GET/PATCH/DELETE /api/auctions/{id}`, `POST /api/auctions/{id}/start`, `POST /api/auctions/{id}/finish`, `POST /api/auctions/{id}/cancel`. `DELETE` отклоняется (409), если у аукциона уже есть лоты.

Sellers: `GET/POST /api/sellers`, `PATCH /api/sellers/{id}`

Buyers: `GET/POST /api/buyers`, `PATCH /api/buyers/{id}`

Lots: `GET /api/lots`, `GET/PATCH/DELETE /api/lots/{id}`, `POST /api/lots`, `GET/POST /api/lots/{id}/bids`. Создание/изменение/удаление лота допускается только для аукциона в статусе `PLANNED` или `ACTIVE`; удаление лота со ставками отклоняется (409). Ставка должна быть не меньше текущей цены + 100 ₽ (`MIN_BID_STEP`). `LotRead` содержит вычисляемое поле `current_price` (цена продажи / максимальная ставка / стартовая цена).

Sales/reports: `GET /api/sales`, `GET /api/sales/{id}`, `POST /api/sales` (тело: `lot_id`, `buyer_id`, `price`; закрывает лот, доступно только для `AVAILABLE`-лота `ACTIVE`-аукциона), `GET /api/reports/revenue`

Swagger: `/docs`.
