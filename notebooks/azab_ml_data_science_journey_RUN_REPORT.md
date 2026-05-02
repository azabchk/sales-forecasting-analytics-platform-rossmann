# Run Report — azab_ml_data_science_journey.ipynb

**Date:** 2026-05-02  
**Author:** Азаб А. М. (Group РИ-420947)  
**Executor:** Claude Code (automated)

---

## Execution Summary

| Item | Status |
|---|---|
| Notebook executed | **Yes** |
| Errors during execution | **None** |
| Code cells | 37 |
| Output notebook size | 144 KB |

---

## Files Created

| File | Description |
|---|---|
| `notebooks/azab_ml_data_science_journey.ipynb` | Source notebook (12 sections, Russian, all cells) |
| `notebooks/azab_ml_data_science_journey_executed.ipynb` | Executed notebook with all cell outputs embedded |
| `notebooks/kpi_overview.png` | 4-panel KPI chart: monthly sales, weekday pattern, promo effect, sales distribution |
| `notebooks/feature_importance.png` | SHAP feature importance bar chart (top 15 features) |
| `notebooks/forecast_demo.png` | 14-day recursive forecast for Store 1 with 80% confidence interval |

---

## Artifacts and Data Used

| Artifact / File | Role in Notebook |
|---|---|
| `data/train.csv` | 1,017,210 rows of historical store sales |
| `data/store.csv` | 1,115-store metadata (type, assortment, competition distance) |
| `ml/features.py` | Imported directly to demonstrate feature engineering pipeline |
| `ml/artifacts/model.joblib` | Loaded for recursive forecast demo (Store 1, 14 days) |
| `ml/artifacts/model_metadata.json` | Source of all reported metrics (MAE, RMSE, WAPE, feature importance, CV) |
| `sql/01_schema.sql` | Read as text, first 40 lines shown for DWH schema overview |
| `sql/02_views_kpi.sql` | Read as text, first 35 lines shown for KPI view definitions |
| `backend/app/services/forecast_service.py` | Key lines shown for integration illustration |
| `backend/app/routers/forecast.py` | Full source shown for REST endpoint overview |

---

## Key Numbers from Execution

| Metric | Value |
|---|---|
| Total sales in dataset | computed from train.csv |
| Promo uplift | ~20% (computed live) |
| Selected model | Ensemble (CatBoost + LightGBM + XGBoost) |
| Validation MAE | 484.6 € |
| Validation RMSE | 776.0 € |
| Validation WAPE | 8.11% |
| Walk-forward CV folds | 2 (30-day windows) |
| Feature count | 43 |
| Top feature | `open` (by SHAP importance) |

---

## Execution Environment

| Item | Detail |
|---|---|
| Python | `ml/.venv311` (Python 3.12) |
| Execution tool | `jupyter nbconvert --execute` |
| Key packages | catboost 1.2.7, lightgbm (installed), xgboost (installed), scikit-learn 1.5.2 |
| Timeout | 300 seconds |
| Matplotlib backend | `Agg` (headless, no GUI required) |

**Fixes applied before execution:**
- Replaced `pkg_resources` with `importlib.metadata` (Python 3.12 compatible)
- Installed `lightgbm` and `xgboost` into `ml/.venv311` (required to load ensemble `model.joblib`)
- Installed `jupyter`, `nbconvert`, `nbclient` into `ml/.venv311`

---

## Skipped Steps

| Step | Reason |
|---|---|
| Full model retraining (`ml/train.py`) | Takes several minutes; results already in `model.joblib` and `model_metadata.json` |
| Live SQL queries against PostgreSQL | Requires a running database with loaded data; skipped gracefully with fallback to CSV |

---

## How to Re-run

```bash
# From project root
ml/.venv311/bin/python3 -m jupyter nbconvert \
  --to notebook \
  --execute notebooks/azab_ml_data_science_journey.ipynb \
  --output "$(pwd)/notebooks/azab_ml_data_science_journey_executed.ipynb" \
  --ExecutePreprocessor.timeout=300
```

To open interactively:

```bash
ml/.venv311/bin/jupyter notebook notebooks/azab_ml_data_science_journey.ipynb
```
