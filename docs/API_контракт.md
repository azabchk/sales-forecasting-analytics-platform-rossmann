# API Контракт

Базовый префикс: `/api/v1`

Формат ответов: `application/json`

## 1. Health

### GET `/health`

Ответ 200:

```json
{
  "status": "ok"
}
```

## 2. Stores

### GET `/stores`

Ответ 200:

```json
[
  {
    "store_id": 1,
    "store_type": "c",
    "assortment": "a"
  }
]
```

## 3. KPI Summary

### GET `/kpi/summary?date_from=YYYY-MM-DD&date_to=YYYY-MM-DD&store_id=optional`

Параметры:
- `date_from` (required)
- `date_to` (required)
- `store_id` (optional)

Пример запроса:

```http
GET /api/v1/kpi/summary?date_from=2015-01-01&date_to=2015-03-31&store_id=10
```

Ответ 200:

```json
{
  "date_from": "2015-01-01",
  "date_to": "2015-03-31",
  "store_id": 10,
  "total_sales": 1234567.89,
  "total_customers": 456789,
  "avg_daily_sales": 13245.67,
  "promo_days": 30,
  "open_days": 85
}
```

## 4. Sales Timeseries

### GET `/sales/timeseries?granularity=daily|monthly&date_from=...&date_to=...&store_id=optional`

Параметры:
- `granularity`: `daily` или `monthly`
- `date_from` (required)
- `date_to` (required)
- `store_id` (optional)

Пример запроса:

```http
GET /api/v1/sales/timeseries?granularity=daily&date_from=2015-01-01&date_to=2015-01-31&store_id=10
```

Ответ 200:

```json
[
  {
    "date": "2015-01-01",
    "store_id": 10,
    "sales": 5234.0,
    "customers": 621.0,
    "promo": 1,
    "open": 1
  }
]
```

## 5. Forecast

### POST `/forecast`

Тело запроса:

```json
{
  "store_id": 10,
  "horizon_days": 30
}
```

Ответ 200:

```json
[
  {
    "date": "2015-08-01",
    "predicted_sales": 7345.21
  },
  {
    "date": "2015-08-02",
    "predicted_sales": 7012.44
  }
]
```

Ошибки:
- `400` — неверные параметры или отсутствуют данные по магазину
- `500` — не найдена модель или внутренняя ошибка

## 6. Promo Impact (дополнительно)

### GET `/kpi/promo-impact?store_id=optional`

Ответ 200:

```json
[
  {
    "store_id": 10,
    "promo_flag": "promo",
    "avg_sales": 8450.3,
    "avg_customers": 710.8,
    "num_days": 120
  },
  {
    "store_id": 10,
    "promo_flag": "no_promo",
    "avg_sales": 6230.1,
    "avg_customers": 560.4,
    "num_days": 240
  }
]
```

## 7. Замечания по интеграции

- Даты передаются в формате ISO `YYYY-MM-DD`.
- Frontend должен задавать `VITE_API_BASE_URL`, например:
  - `http://localhost:8000/api/v1`
- CORS-настройка backend должна включать origin frontend (обычно `http://localhost:5173`).
