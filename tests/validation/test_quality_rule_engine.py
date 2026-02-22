from __future__ import annotations

import sys
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parents[2]
SRC_PATH = PROJECT_ROOT / "src"
if str(SRC_PATH) not in sys.path:
    sys.path.insert(0, str(SRC_PATH))

from validation.input_contract_models import InputContract, load_input_contract
from validation.input_validator import validate_csv_file
from validation.quality_rule_engine import evaluate_quality_rules
from validation.schema_unifier import unify_validated_dataframe


@pytest.fixture(scope="module")
def contract_path() -> Path:
    return PROJECT_ROOT / "config" / "input_contract" / "contract_v1.yaml"


@pytest.fixture(scope="module")
def fixtures_dir() -> Path:
    return PROJECT_ROOT / "tests" / "fixtures" / "input_samples"


def _evaluate_train_file(contract_path: Path, file_path: Path) -> dict:
    contract = load_input_contract(contract_path)
    validation_result = validate_csv_file(
        file_path=file_path,
        contract=contract,
        profile_name="rossmann_train",
    )
    assert validation_result.report["status"] != "FAIL"

    unification = unify_validated_dataframe(
        validation_result=validation_result,
        contract=contract,
        profile_name="rossmann_train",
        source_file_name=file_path.name,
    )
    quality_report = evaluate_quality_rules(
        dataframe=unification.unified_dataframe,
        profile=contract.profiles["rossmann_train"],
    )
    return quality_report.to_dict()


def _rule_status(report: dict, rule_id: str) -> str:
    rule_map = {rule["rule_id"]: rule["status"] for rule in report["rules"]}
    return str(rule_map[rule_id])


def test_between_rule_sales_non_negative(contract_path: Path, fixtures_dir: Path):
    report = _evaluate_train_file(contract_path, fixtures_dir / "rossmann_train_semantic_fail_sales.csv")
    assert _rule_status(report, "sales_non_negative") == "FAIL"
    assert report["status"] == "FAIL"


def test_accepted_values_rule_day_of_week(contract_path: Path, fixtures_dir: Path):
    report = _evaluate_train_file(contract_path, fixtures_dir / "rossmann_train_semantic_fail_day.csv")
    assert _rule_status(report, "day_of_week_allowed") == "FAIL"
    assert report["status"] == "FAIL"


def test_max_null_ratio_rule(contract_path: Path, fixtures_dir: Path):
    report = _evaluate_train_file(contract_path, fixtures_dir / "rossmann_train_semantic_warn.csv")
    assert _rule_status(report, "customers_null_ratio") == "WARN"
    assert report["status"] == "WARN"


def test_composite_unique_rule(contract_path: Path, fixtures_dir: Path):
    report = _evaluate_train_file(contract_path, fixtures_dir / "rossmann_train_semantic_fail_duplicate.csv")
    assert _rule_status(report, "train_pk_unique") == "FAIL"
    assert report["status"] == "FAIL"


def test_contract_loading_without_quality_rules_is_backward_compatible():
    payload = {
        "contract_version": "v1",
        "format": "csv",
        "limits": {"max_rows": 100, "max_file_size_mb": 1},
        "rules": {"allow_extra_columns": True, "strict_types": False},
        "profiles": {
            "minimal_profile": {
                "columns": [
                    {
                        "canonical_name": "store_id",
                        "required": True,
                        "dtype": "int",
                        "aliases": ["Store"],
                    }
                ]
            }
        },
    }

    contract = InputContract.from_dict(payload)
    assert contract.profiles["minimal_profile"].quality_rules.has_rules is False
