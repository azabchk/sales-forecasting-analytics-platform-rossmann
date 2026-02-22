# ML Module

Modeling package for store-level daily sales forecasting.

## What It Does

- reads prepared fact/dimension data from PostgreSQL
- builds time-series features (lags, rolling means/std, trend index)
- applies target transformation (`log1p`) for robust training
- evaluates Ridge baseline and CatBoost grid candidates
- selects model by validation RMSE
- exports:
  - `ml/artifacts/model.joblib`
  - `ml/artifacts/model_metadata.json`

## Metrics

Validation metrics include:
- `MAE`
- `RMSE`
- `MAPE`
- `WAPE`

## Run

```bash
cd ml
python3 -m venv .venv
source .venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt
python train.py --config config.yaml
python evaluate.py --config config.yaml
```

## Offline Prediction Script

`predict.py` can run recursive forecasts from CLI using saved model artifacts.

## Chatbot Intent Model

Train the chatbot intent classifier artifact used by backend chat routing:

```bash
cd ml
source .venv/bin/activate
python train_chatbot.py --config config.yaml
```

Output:
- `ml/artifacts/chat_intent_model.joblib`
