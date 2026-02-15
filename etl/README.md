# ETL модуль

Модуль выполняет загрузку `train.csv` и `store.csv` в PostgreSQL Star Schema.

## Что делает

- читает сырые CSV из `../data`
- очищает и приводит типы
- строит и загружает:
  - `dim_store`
  - `dim_date`
  - `fact_sales_daily`
- обеспечивает идемпотентность через стратегию `truncate + reload` в одной транзакции
- запускает проверки качества данных

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

## Проверка качества данных

```bash
cd etl
python data_quality.py --config config.yaml
```

## Ожидаемый результат

- таблицы `dim_store`, `dim_date`, `fact_sales_daily` заполнены
- отчет `data_quality.py` выводит статус по проверкам
