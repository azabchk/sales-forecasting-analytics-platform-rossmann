"""
Generate minimal synthetic Rossmann CSV data for CI smoke tests.
Only runs if data/train.csv or data/store.csv are missing.
"""
from __future__ import annotations

import csv
import random
from datetime import date, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = ROOT / "data"
DATA_DIR.mkdir(exist_ok=True)

TRAIN_CSV = DATA_DIR / "train.csv"
STORE_CSV = DATA_DIR / "store.csv"

N_STORES = 10
# 500 days gives enough history for the lag_364 feature (requires ≥400 days)
N_DAYS = 500
START_DATE = date(2013, 1, 1)

STORE_TYPES = ["a", "b", "c", "d"]
ASSORTMENTS = ["a", "b", "c"]


def generate_store_csv() -> None:
    if STORE_CSV.exists():
        print(f"[smoke-data] {STORE_CSV} already exists, skipping.")
        return
    rng = random.Random(42)
    rows = []
    for store_id in range(1, N_STORES + 1):
        rows.append({
            "Store": store_id,
            "StoreType": rng.choice(STORE_TYPES),
            "Assortment": rng.choice(ASSORTMENTS),
            "CompetitionDistance": rng.randint(200, 20000),
            "CompetitionOpenSinceMonth": rng.randint(1, 12),
            "CompetitionOpenSinceYear": rng.randint(2000, 2012),
            "Promo2": rng.randint(0, 1),
            "Promo2SinceWeek": rng.randint(1, 52),
            "Promo2SinceYear": rng.randint(2009, 2013),
            "PromoInterval": rng.choice(["", "Jan,Apr,Jul,Oct", "Feb,May,Aug,Nov"]),
        })
    _write_csv(STORE_CSV, rows)
    print(f"[smoke-data] Generated {STORE_CSV} ({N_STORES} stores).")


def generate_train_csv() -> None:
    if TRAIN_CSV.exists():
        print(f"[smoke-data] {TRAIN_CSV} already exists, skipping.")
        return
    rng = random.Random(42)
    rows = []
    for store_id in range(1, N_STORES + 1):
        for day_offset in range(N_DAYS):
            d = START_DATE + timedelta(days=day_offset)
            day_of_week = d.isoweekday()  # 1=Mon … 7=Sun
            is_open = 0 if day_of_week == 7 else 1
            sales = round(rng.uniform(3000, 12000), 2) if is_open else 0
            rows.append({
                "Store": store_id,
                "DayOfWeek": day_of_week,
                "Date": d.isoformat(),
                "Sales": sales,
                "Customers": int(sales / 10) if is_open else 0,
                "Open": is_open,
                "Promo": rng.randint(0, 1),
                "StateHoliday": "0",
                "SchoolHoliday": rng.randint(0, 1),
            })
    _write_csv(TRAIN_CSV, rows)
    total = N_STORES * N_DAYS
    print(f"[smoke-data] Generated {TRAIN_CSV} ({total} rows).")


def _write_csv(path: Path, rows: list[dict]) -> None:
    with open(path, "w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=list(rows[0].keys()), quoting=csv.QUOTE_NONNUMERIC)
        writer.writeheader()
        writer.writerows(rows)


if __name__ == "__main__":
    generate_store_csv()
    generate_train_csv()
