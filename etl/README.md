# ETL модуль

Модуль выполняет загрузку `train.csv` и `store.csv` в PostgreSQL Star Schema.

## Что делает

- читает сырые CSV из `../data`
- выполняет pre-ETL валидацию и унификацию входов по контракту
- очищает и приводит типы
- строит и загружает:
  - `dim_store`
  - `dim_date`
  - `fact_sales_daily`
- обеспечивает идемпотентность через стратегию `truncate + reload` в одной транзакции
- запускает проверки качества данных

Документация контракта входов:
- `../docs/Input_Data_Contract.md`

## Подготовка (Ubuntu 24.04)

```bash
cd etl
python3 -m venv .venv
source .venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt
```

## Переменные окружения

Создайте `.env` в корне репозитория на основе `.env.example`.

Используется переменная:
- `DATABASE_URL` (например: `postgresql+psycopg2://rossmann_user:change_me@localhost:5432/rossmann`)

## Запуск ETL

```bash
cd etl
python etl_load.py --config config.yaml
```

### Режимы preflight (validation + unification)

По умолчанию preflight выключен (`mode: off`), чтобы не ломать текущий demo-flow.

- `off`: ETL использует сырые CSV без preflight
- `report_only`: preflight запускается и сохраняет артефакты, но ETL читает сырые CSV
- `enforce`: FAIL останавливает ETL, PASS/WARN переключает ETL на unified CSV

С Milestone 4 preflight также выполняет semantic quality rules на unified данных:
- column rules: `between`, `accepted_values`, `max_null_ratio`
- table rules: `composite_unique`, `row_count_between`
- у каждого правила есть severity: `WARN` или `FAIL`
- semantic `FAIL` блокирует ETL только в режиме `enforce`

Примеры запуска:

```bash
# 1) default (off)
cd etl
python etl_load.py --config config.yaml

# 2) report_only
python etl_load.py --config config.yaml --preflight-mode report_only

# 3) enforce
python etl_load.py --config config.yaml --preflight-mode enforce
```

Артефакты preflight:

- `etl/reports/preflight/<run_id>/train/`
- `etl/reports/preflight/<run_id>/store/`
  - `validation_report.json`
  - `semantic_report.json`
  - `manifest.json` (включает semantic section)
  - `preflight_report.json` (сводный отчет)

## Проверка качества данных

```bash
cd etl
python data_quality.py --config config.yaml
```

## Ожидаемый результат

- таблицы `dim_store`, `dim_date`, `fact_sales_daily` заполнены
- отчет `data_quality.py` выводит статус по проверкам
