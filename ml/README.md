# ML модуль

Модуль отвечает за обучение и применение модели прогноза ежедневных продаж по магазину.

## Функциональность

- извлечение данных из PostgreSQL DWH
- построение признаков:
  - лаги `1, 7, 14, 28`
  - скользящие средние `7, 14, 28`
  - календарные признаки
  - promo/holiday + метаданные магазина
- time-based split (без случайного разбиения)
- сравнение моделей:
  - Baseline: `Ridge`
  - Advanced: `CatBoostRegressor`
- метрики: `MAE`, `RMSE`
- сохранение артефактов в `ml/artifacts/`

## Запуск (Ubuntu 24.04)

```bash
cd ml
python3 -m venv .venv
source .venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt
python train.py --config config.yaml
python evaluate.py --config config.yaml
```

## Артефакты

- `ml/artifacts/model.joblib` — сериализованная модель + служебные поля
- `ml/artifacts/model_metadata.json` — дата обучения, метрики, список признаков, периоды train/val

## Инференс

Скрипт `predict.py` используется backend-сервисом для прогноза на горизонт `N` дней.
