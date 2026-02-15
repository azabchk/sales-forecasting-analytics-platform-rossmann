# Frontend (React + TypeScript)

Интерфейс аналитической платформы с тремя разделами:
- Overview (KPI + общий график)
- Store Analytics (магазин, дневная динамика, promo impact)
- Forecast (прогноз на N дней)

## Подготовка (Ubuntu 24.04)

```bash
cd frontend
npm install
```

## Переменные окружения

Создайте файл `frontend/.env`:

```bash
cp .env.example .env
```

## Запуск

```bash
cd frontend
npm run dev
```

Приложение будет доступно на `http://localhost:5173`.
