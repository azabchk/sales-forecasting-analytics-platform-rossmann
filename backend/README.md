# Backend (FastAPI)

Backend предоставляет API для:
- мониторинга сервиса (`/health`)
- списка магазинов
- KPI-агрегаций и временных рядов
- ML-прогноза продаж

## Подготовка (Ubuntu 24.04)

```bash
cd backend
python3 -m venv .venv
source .venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt
```

## Конфигурация

Создайте `.env` в корне репозитория (`../.env`) и заполните:
- `DATABASE_URL`
- `CORS_ORIGINS`
- `MODEL_PATH`
- `MODEL_METADATA_PATH`
- `BACKEND_HOST`
- `BACKEND_PORT`

## Запуск

```bash
cd backend
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

Документация Swagger: `http://localhost:8000/docs`

## API base

Все рабочие эндпоинты находятся под префиксом: `/api/v1`
