# Frontend (React + TypeScript)

Professional analytics UI with three pages:
- `Overview` - KPI monitoring and portfolio trend view
- `Store Analytics` - store filter, daily sales/customers trend, promo impact table
- `Forecast` - scenario controls, forecast chart, confidence interval lines

## Setup

```bash
cd frontend
cp .env.example .env
npm install
```

## Run

```bash
npm run dev
```

App URL: `http://localhost:5173`

## Environment Variable

`VITE_API_BASE_URL=http://localhost:8000/api/v1`
