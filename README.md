# Aqiq Analytics Platform
### Sales Forecasting & Analytics System — Rossmann Dataset

> **Diploma Project** — Full-stack machine learning platform for retail sales forecasting, scenario planning, and data operations management.

---

## Table of Contents

- [Overview](#overview)
- [Architecture](#architecture)
- [Features](#features)
- [Tech Stack](#tech-stack)
- [Machine Learning Pipeline](#machine-learning-pipeline)
- [Quick Start](#quick-start)
- [API Reference](#api-reference)
- [Authentication](#authentication)
- [Project Structure](#project-structure)

---

## Overview

**Aqiq Analytics Platform** is an end-to-end analytics system built on the [Rossmann Store Sales](https://www.kaggle.com/c/rossmann-store-sales) dataset. It combines a production-grade REST API, an interactive React dashboard, and a multi-model ML pipeline to deliver:

- **Daily sales forecasting** up to 180 days ahead per store
- **What-if scenario planning** with price elasticity, promo modes, and demand shifts
- **Portfolio-level forecasting** across up to 50 stores simultaneously
- **Real-time KPI analytics** with promo impact analysis
- **Data quality governance** via preflight validation and alert policies
- **AI-powered chat assistant** for natural language analytics queries

---

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                     Browser (React 18)                      │
│  Login → Dashboard → Forecast / Scenario / AI Assistant     │
└──────────────────────────┬──────────────────────────────────┘
                           │  HTTPS / JWT Bearer
┌──────────────────────────▼──────────────────────────────────┐
│              FastAPI Backend  (Python 3.12)                  │
│  Auth · Forecast · KPI · Scenario · Chat · Diagnostics      │
│  Rate Limiting (slowapi) · JWT + Refresh Token              │
└────────┬─────────────────┬───────────────────────────────────┘
         │                 │
┌────────▼──────┐  ┌───────▼───────────────────────────────────┐
│  PostgreSQL   │  │         ML Artifacts (joblib)              │
│  Star Schema  │  │  CatBoost · LightGBM · XGBoost · Ridge     │
│  + 8 tables   │  │  Ensemble · SHAP Importance                │
└───────────────┘  └───────────────────────────────────────────┘
         │
┌────────▼──────────────────────────────────────────────────────┐
│  Monitoring: Prometheus + Grafana + AlertManager              │
└───────────────────────────────────────────────────────────────┘
```

---

## Features

### Analytics & Forecasting

| Feature | Description |
|---|---|
| **Sales Forecast** | Recursive multi-step forecasting per store, 1–180 days |
| **Confidence Intervals** | Horizon-scaled uncertainty bands (3%/day growth) |
| **Batch Forecast** | Portfolio forecast across up to 50 stores simultaneously |
| **Scenario Lab (V2)** | Price elasticity · promo modes · demand shift · store segments |
| **KPI Dashboard** | Total sales · customers · avg daily · promo days |
| **Store Comparison** | Side-by-side metrics for up to 10 stores |
| **Promo Impact** | Avg sales on promo vs non-promo days per store |

### ML Pipeline

| Feature | Description |
|---|---|
| **4-model grid search** | Ridge · CatBoost (6 candidates) · LightGBM (3) · XGBoost (3) |
| **Auto ensemble** | Averages top-3 tree models if composite score improves |
| **SHAP importance** | Per-feature mean absolute SHAP values on validation set |
| **Walk-forward CV** | 2-fold × 30-day rolling windows for stability reporting |
| **Drift detection** | Compares latest vs previous experiment metrics |
| **Retrain trigger** | One-click retraining from the UI |

### Data Operations

| Feature | Description |
|---|---|
| **Preflight validation** | Schema + semantic quality checks before data load |
| **Alert policies** | Threshold-based alerts on preflight metrics |
| **Webhook notifications** | HMAC-signed delivery with retry + dead-letter + replay |
| **Data Pipeline page** | Freshness indicators · run history · manual trigger |
| **Contract registry** | Versioned input data contracts with schema profiles |

### Platform & Security

| Feature | Description |
|---|---|
| **JWT Auth** | 8-hour access token + 7-day refresh token |
| **Auto token refresh** | Transparent renewal on 401 — no session interruption |
| **Rate limiting** | 200 req/min global · 10 req/min on login (brute-force protection) |
| **User management** | Admin creates/activates/deactivates analyst accounts |
| **Change password** | Users can update their own password from the UI |
| **Prometheus metrics** | preflight runs · alerts · notifications · delivery latency |

### AI Assistant

| Intent | Example query |
|---|---|
| `forecast` | "Forecast store 1 for 30 days" |
| `kpi_summary` | "Show KPI for 2015-07-01 to 2015-07-31" |
| `promo_impact` | "What is the promo impact for store 5?" |
| `top_stores` | "Show top 5 stores by total sales" |
| `model_summary` | "What is the model accuracy?" |
| `system_summary` | "How many stores are in the system?" |
| `data_status` | "What is the data pipeline status?" |
| `compare_stores` | "Compare store 1 and store 2" |

---

## Tech Stack

### Backend

| Layer | Technology |
|---|---|
| API Framework | FastAPI 0.115 + Uvicorn |
| Database | PostgreSQL 16 (star schema) |
| ORM / Queries | SQLAlchemy 2.0 |
| Auth | python-jose (JWT) + passlib/bcrypt |
| Rate Limiting | slowapi |
| Scheduling | APScheduler 3.10 |
| Validation | Pydantic v2 |

### Machine Learning

| Library | Use |
|---|---|
| CatBoost 1.2 | Primary gradient boosting model |
| LightGBM ≥4.0 | Second tree model in comparison |
| XGBoost ≥2.0 | Third tree model in comparison |
| scikit-learn 1.5 | Ridge baseline · TF-IDF chatbot pipeline |
| pandas 2.2 | Feature engineering |
| joblib | Model serialization |

### Frontend

| Library | Use |
|---|---|
| React 18 + TypeScript | UI framework |
| Vite 5 | Build tool |
| React Router v6 | Client-side routing |
| TanStack Query | Server state management |
| Recharts | Charts and visualizations |
| Axios | HTTP client |

---

## Machine Learning Pipeline

### Feature Engineering (43 features)

```
Calendar     → day_of_week, month, quarter, week_of_year, is_weekend,
               day_of_month, is_month_start, is_month_end

Lag features → lag_1, lag_3, lag_7, lag_14, lag_21, lag_28, lag_364

Rolling      → rolling_mean_7/14/28/56, rolling_std_7/14/28/56

Derived      → lag_1_to_mean_7_ratio, sales_velocity,
               lag_364_to_mean_28_ratio

Promo        → promo_density_7, promo_density_14

Store meta   → competition_distance, competition_distance_log, promo2

Categorical  → state_holiday, store_type, assortment  (one-hot)
```

### Model Selection Logic

```
For each model family:
  → Grid search over parameter candidates
  → Evaluate on holdout (last 90 days)
  → Composite score = 0.5 × NRMSE + 0.5 × WAPE

Then:
  → If ensemble(CatBoost + LightGBM + XGBoost) < best individual
      → Select ensemble
  → Else → Select best individual

Final: SHAP values + walk-forward CV for robustness reporting
```

### Forecast Inference (Recursive)

```
For step 1..horizon_days:
  1. Build feature row from rolling sales_history
  2. One-hot encode categoricals → reindex to training columns
  3. model.predict(x) → raw prediction
  4. Inverse log1p transform
  5. Apply demand_shift_pct multiplier
  6. Clip to [prediction_floor, prediction_cap]
  7. Interval: pred ± z × σ × (1 + 0.03 × min(step-1, 89))
  8. Append prediction to sales_history for next step
```

---

## Quick Start

### Prerequisites
- Python 3.11+
- Node.js 18+
- PostgreSQL 14+

### 1 — Clone and configure

```bash
git clone <repo>
cd sales-forecasting-analytics-platform-rossmann
cp .env.example .env
# Edit .env — set DATABASE_URL and SECRET_KEY
```

### 2 — Backend setup

```bash
cd backend
python -m venv .venv311
source .venv311/bin/activate          # Windows: .venv311\Scripts\activate
pip install -r requirements.txt
```

### 3 — Initialize database

```bash
python scripts/init_db.py
```

### 4 — Create first admin account

```bash
python scripts/create_admin.py
# Enter email, username, password when prompted
```

### 5 — Frontend setup

```bash
cd frontend
npm install
```

### 6 — Start services

```bash
# Linux — one command
bash scripts/start_local_linux.sh

# Or manually:
# Terminal 1
cd backend
python -m uvicorn app.main:app --host 0.0.0.0 --port 8001

# Terminal 2
cd frontend
VITE_API_BASE_URL=http://localhost:8001/api/v1 npm run dev
```

### 7 — Train ML models

```bash
# Sales forecast model (~5-15 min depending on data size)
cd ml && python train.py --config config.yaml

# Chatbot intent classifier (~30 sec)
cd ml && python train_chatbot.py --config config.yaml
```

### Access

| Service | URL |
|---|---|
| Frontend | `http://localhost:5173` |
| Backend API | `http://localhost:8001/api/v1` |
| Interactive API Docs | `http://localhost:8001/docs` |

---

## API Reference

### Login

```http
POST /api/v1/auth/login
Content-Type: application/json

{
  "email": "admin@example.com",
  "password": "your_password"
}
```

Response:
```json
{
  "access_token": "eyJ...",
  "refresh_token": "eyJ...",
  "token_type": "bearer",
  "user": { "id": 1, "username": "admin", "role": "admin" }
}
```

### Token Refresh

```http
POST /api/v1/auth/refresh
{ "refresh_token": "eyJ..." }
```

### All protected endpoints

```http
Authorization: Bearer <access_token>
```

### Core endpoints

```http
POST   /api/v1/forecast                    # Single store forecast
POST   /api/v1/forecast/batch              # Portfolio forecast
POST   /api/v1/forecast/scenario           # Scenario vs baseline
POST   /api/v1/scenario/run               # V2 scenario (store or segment)
GET    /api/v1/kpi/summary                 # KPI metrics
GET    /api/v1/kpi/promo-impact            # Promo uplift
GET    /api/v1/sales/timeseries            # Time-series data
GET    /api/v1/stores                      # Paginated store list
GET    /api/v1/stores/comparison           # Multi-store comparison
POST   /api/v1/chat/query                  # AI assistant
GET    /api/v1/model/metadata              # Current model info
POST   /api/v1/ml/retrain                  # Trigger retraining
GET    /api/v1/ml/drift                    # Model drift detection
GET    /api/v1/auth/users                  # List users (admin)
POST   /api/v1/auth/register               # Create user (admin)
PATCH  /api/v1/auth/me/password            # Change password
```

---

## Authentication

Two-token JWT strategy:

| Token | Expiry | Purpose |
|---|---|---|
| **Access token** | 8 hours | API authorization |
| **Refresh token** | 7 days | Silent access token renewal |

When the access token expires, the Axios interceptor:
1. Intercepts the 401 response
2. Calls `POST /auth/refresh` with the stored refresh token
3. Updates both tokens in `localStorage`
4. Retries the original request automatically
5. Queues any concurrent requests during the refresh window

**Roles:**

| Role | Permissions |
|---|---|
| `admin` | Full access + user management + retrain |
| `analyst` | All analytics features, read-only for users |

---

## Project Structure

```
├── backend/
│   ├── app/
│   │   ├── main.py            Entry point · middleware · routers
│   │   ├── config.py          Settings (pydantic-settings)
│   │   ├── db.py              SQLAlchemy engine
│   │   ├── schemas.py         Pydantic models (70+ schemas)
│   │   ├── routers/           12 API router modules
│   │   ├── services/          15 business logic services
│   │   └── security/          JWT · bcrypt · rate limiting
│   └── tests/                 pytest suite (20+ test files)
│
├── ml/
│   ├── train.py               Multi-model training pipeline
│   ├── train_chatbot.py       Intent classifier (TF-IDF + LogReg)
│   ├── features.py            Feature engineering
│   ├── config.yaml            Hyperparameter grid definitions
│   └── artifacts/             model.joblib · chat_intent_model.joblib
│
├── frontend/
│   └── src/
│       ├── pages/             13 page components
│       ├── components/        Reusable UI (ErrorBoundary, Charts, Table)
│       ├── contexts/          AuthContext (JWT + auto-refresh)
│       ├── api/               Axios client + 50+ typed endpoint functions
│       └── lib/               i18n · theme · CSV export · formatting
│
├── sql/
│   ├── 01_schema.sql          dim_store · dim_date · fact_sales_daily
│   ├── 02_views_kpi.sql       6 analytics views
│   ├── 03_indexes.sql         Performance indexes
│   ├── 04_v2_ecosystem.sql    data_source · run registries · ML experiments
│   └── 05_users.sql           User accounts table
│
├── src/etl/                   Shared SQLAlchemy registries
├── config/                    Alert policies · notification channels YAML
├── monitoring/                Prometheus · Grafana · AlertManager configs
├── scripts/                   Bootstrap · start · stop · create_admin
└── docker-compose.yml         PostgreSQL + backend for local development
```

---

*Built with FastAPI · React 18 · CatBoost · LightGBM · XGBoost · PostgreSQL*

*Diploma project — 2026*
