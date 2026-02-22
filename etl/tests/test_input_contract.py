from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from etl.input_contract import validate_and_unify_inputs


def _base_validation_config() -> dict:
    return {
        "encodings": ["utf-8", "utf-8-sig"],
        "file_limits": {
            "max_file_size_mb": 10,
            "max_rows": 10000,
        },
        "profile_mapping": {
            "train": "rossmann_train",
            "store": "rossmann_store",
        },
        "policy": {
            "on_unknown_columns": "warn",
            "on_duplicates": "warn",
            "on_invalid_dates": "fail",
            "type_coercion_fail_threshold": 0,
            "null_threshold_required": 0.0,
        },
        "source_profiles": {
            "rossmann_train": {
                "required_columns": ["store_id", "day_of_week", "full_date", "sales"],
                "optional_columns": ["customers", "open", "promo", "state_holiday", "school_holiday"],
                "aliases": {
                    "store_id": ["Store"],
                    "day_of_week": ["DayOfWeek"],
                    "full_date": ["Date"],
                    "sales": ["Sales"],
                    "customers": ["Customers"],
                    "open": ["Open"],
                    "promo": ["Promo"],
                    "state_holiday": ["StateHoliday"],
                    "school_holiday": ["SchoolHoliday"],
                },
                "dtypes": {
                    "store_id": "int",
                    "day_of_week": "int",
                    "full_date": "date",
                    "sales": "float",
                    "customers": "float",
                    "open": "int",
                    "promo": "int",
                    "state_holiday": "string",
                    "school_holiday": "int",
                },
                "duplicate_subset": ["store_id", "full_date"],
                "ranges": {
                    "sales": {"min": 0},
                    "promo": {"allowed": [0, 1]},
                    "open": {"allowed": [0, 1]},
                    "school_holiday": {"allowed": [0, 1]},
                },
            },
            "rossmann_store": {
                "required_columns": ["store_id"],
                "optional_columns": ["store_type", "assortment", "competition_distance", "promo2"],
                "aliases": {
                    "store_id": ["Store"],
                    "store_type": ["StoreType"],
                    "assortment": ["Assortment"],
                    "competition_distance": ["CompetitionDistance"],
                    "promo2": ["Promo2"],
                },
                "dtypes": {
                    "store_id": "int",
                    "store_type": "string",
                    "assortment": "string",
                    "competition_distance": "float",
                    "promo2": "int",
                },
                "duplicate_subset": ["store_id"],
                "ranges": {
                    "competition_distance": {"min": 0},
                    "promo2": {"allowed": [0, 1]},
                },
            },
        },
    }


def _write_csv(path: Path, rows: list[dict]) -> None:
    pd.DataFrame(rows).to_csv(path, index=False)


def test_valid_rossmann_inputs_pass(tmp_path: Path):
    train_csv = tmp_path / "train.csv"
    store_csv = tmp_path / "store.csv"

    _write_csv(
        train_csv,
        [
            {
                "Store": 1,
                "DayOfWeek": 1,
                "Date": "2015-07-01",
                "Sales": 1000,
                "Customers": 100,
                "Open": 1,
                "Promo": 1,
                "StateHoliday": "0",
                "SchoolHoliday": 0,
            }
        ],
    )
    _write_csv(
        store_csv,
        [
            {
                "Store": 1,
                "StoreType": "a",
                "Assortment": "a",
                "CompetitionDistance": 100,
                "Promo2": 1,
            }
        ],
    )

    result = validate_and_unify_inputs(
        train_csv=str(train_csv),
        store_csv=str(store_csv),
        validation_config=_base_validation_config(),
    )

    assert result["report"]["status"] == "PASS"
    assert "store_id" in result["dataframes"]["train"].columns
    assert "full_date" in result["dataframes"]["train"].columns


def test_missing_required_column_fails(tmp_path: Path):
    train_csv = tmp_path / "train.csv"
    store_csv = tmp_path / "store.csv"

    _write_csv(train_csv, [{"Store": 1, "DayOfWeek": 1, "Date": "2015-07-01"}])
    _write_csv(store_csv, [{"Store": 1}])

    result = validate_and_unify_inputs(
        train_csv=str(train_csv),
        store_csv=str(store_csv),
        validation_config=_base_validation_config(),
    )

    assert result["report"]["status"] == "FAIL"
    assert any("missing required columns" in msg for msg in result["report"]["errors"])


def test_invalid_date_policy_fail(tmp_path: Path):
    cfg = _base_validation_config()
    cfg["policy"]["on_invalid_dates"] = "fail"

    train_csv = tmp_path / "train.csv"
    store_csv = tmp_path / "store.csv"
    _write_csv(
        train_csv,
        [
            {
                "Store": 1,
                "DayOfWeek": 1,
                "Date": "bad-date",
                "Sales": 1000,
                "Open": 1,
                "Promo": 1,
                "SchoolHoliday": 0,
            }
        ],
    )
    _write_csv(store_csv, [{"Store": 1}])

    result = validate_and_unify_inputs(
        train_csv=str(train_csv),
        store_csv=str(store_csv),
        validation_config=cfg,
    )

    assert result["report"]["status"] == "FAIL"


def test_invalid_date_policy_drop(tmp_path: Path):
    cfg = _base_validation_config()
    cfg["policy"]["on_invalid_dates"] = "drop"
    cfg["policy"]["type_coercion_fail_threshold"] = 10

    train_csv = tmp_path / "train.csv"
    store_csv = tmp_path / "store.csv"
    _write_csv(
        train_csv,
        [
            {
                "Store": 1,
                "DayOfWeek": 1,
                "Date": "bad-date",
                "Sales": 1000,
                "Open": 1,
                "Promo": 1,
                "SchoolHoliday": 0,
            },
            {
                "Store": 1,
                "DayOfWeek": 2,
                "Date": "2015-07-02",
                "Sales": 900,
                "Open": 1,
                "Promo": 0,
                "SchoolHoliday": 0,
            },
        ],
    )
    _write_csv(store_csv, [{"Store": 1}])

    result = validate_and_unify_inputs(
        train_csv=str(train_csv),
        store_csv=str(store_csv),
        validation_config=cfg,
    )

    assert result["report"]["status"] == "PASS_WITH_WARNINGS"
    assert len(result["dataframes"]["train"]) == 1


def test_duplicates_unknown_columns_and_alias_mapping(tmp_path: Path):
    cfg = _base_validation_config()
    cfg["policy"]["on_duplicates"] = "drop"
    cfg["policy"]["type_coercion_fail_threshold"] = 5

    train_csv = tmp_path / "train.csv"
    store_csv = tmp_path / "store.csv"

    _write_csv(
        train_csv,
        [
            {
                "Store": 1,
                "DayOfWeek": 1,
                "Date": "2015-07-01",
                "Sales": 1000,
                "Open": 1,
                "Promo": 1,
                "SchoolHoliday": 0,
                "CustomSourceCol": "X",
            },
            {
                "Store": 1,
                "DayOfWeek": 1,
                "Date": "2015-07-01",
                "Sales": 1000,
                "Open": 1,
                "Promo": 1,
                "SchoolHoliday": 0,
                "CustomSourceCol": "X",
            },
        ],
    )
    _write_csv(
        store_csv,
        [
            {
                "Store": 1,
                "StoreType": "a",
                "Assortment": "a",
                "CompetitionDistance": 100,
                "Promo2": 1,
            }
        ],
    )

    result = validate_and_unify_inputs(
        train_csv=str(train_csv),
        store_csv=str(store_csv),
        validation_config=cfg,
    )

    assert result["report"]["status"] == "PASS_WITH_WARNINGS"
    assert "store_id" in result["dataframes"]["train"].columns
    assert len(result["dataframes"]["train"]) == 1
    assert any("unknown columns" in warning for warning in result["report"]["warnings"])
