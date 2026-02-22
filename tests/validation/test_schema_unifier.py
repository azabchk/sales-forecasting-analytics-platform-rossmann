from __future__ import annotations

import sys
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parents[2]
SRC_PATH = PROJECT_ROOT / "src"
if str(SRC_PATH) not in sys.path:
    sys.path.insert(0, str(SRC_PATH))

from validation.input_contract_models import load_input_contract
from validation.input_validator import validate_csv_file
from validation.schema_unifier import unify_validated_dataframe


@pytest.fixture(scope="module")
def contract_path() -> Path:
    return PROJECT_ROOT / "config" / "input_contract" / "contract_v1.yaml"


@pytest.fixture(scope="module")
def fixtures_dir() -> Path:
    return PROJECT_ROOT / "tests" / "fixtures" / "input_samples"


def test_aliases_are_renamed_and_canonical_order_enforced(contract_path: Path, fixtures_dir: Path):
    contract = load_input_contract(contract_path)
    validation_result = validate_csv_file(
        file_path=fixtures_dir / "rossmann_train_alias_mixed.csv",
        contract=contract,
        profile_name="rossmann_train",
    )

    unification = unify_validated_dataframe(
        validation_result=validation_result,
        contract=contract,
        profile_name="rossmann_train",
        source_file_name="rossmann_train_alias_mixed.csv",
    )

    expected_order = [col.strip().lower() for col in contract.profiles["rossmann_train"].canonical_order]
    assert list(unification.unified_dataframe.columns[: len(expected_order)]) == expected_order
    assert unification.manifest["renamed_columns"].get("storeid") == "store_id"
    assert unification.manifest["renamed_columns"].get("date") == "full_date"


def test_type_coercion_stats_are_reported(contract_path: Path, fixtures_dir: Path):
    contract = load_input_contract(contract_path)
    validation_result = validate_csv_file(
        file_path=fixtures_dir / "rossmann_train_alias_mixed.csv",
        contract=contract,
        profile_name="rossmann_train",
    )

    unification = unify_validated_dataframe(
        validation_result=validation_result,
        contract=contract,
        profile_name="rossmann_train",
        source_file_name="rossmann_train_alias_mixed.csv",
    )

    coercion = unification.manifest["coercion_stats"]
    assert coercion["day_of_week"]["invalid_to_null"] >= 1
    assert coercion["full_date"]["invalid_to_null"] >= 1
    assert coercion["sales"]["invalid_to_null"] >= 1


def test_extra_columns_dropped_when_rule_enabled(contract_path: Path, fixtures_dir: Path):
    contract = load_input_contract(contract_path)
    contract.drop_unknown_columns = True

    validation_result = validate_csv_file(
        file_path=fixtures_dir / "rossmann_train_extra_columns.csv",
        contract=contract,
        profile_name="rossmann_train",
    )

    unification = unify_validated_dataframe(
        validation_result=validation_result,
        contract=contract,
        profile_name="rossmann_train",
        source_file_name="rossmann_train_extra_columns.csv",
    )

    assert "CustomMetric" not in unification.unified_dataframe.columns
    assert "CustomMetric" in unification.manifest["extra_columns_dropped"]


def test_extra_columns_retained_when_rule_disabled(contract_path: Path, fixtures_dir: Path):
    contract = load_input_contract(contract_path)
    contract.drop_unknown_columns = False

    validation_result = validate_csv_file(
        file_path=fixtures_dir / "rossmann_train_extra_columns.csv",
        contract=contract,
        profile_name="rossmann_train",
    )

    unification = unify_validated_dataframe(
        validation_result=validation_result,
        contract=contract,
        profile_name="rossmann_train",
        source_file_name="rossmann_train_extra_columns.csv",
    )

    assert "CustomMetric" in unification.unified_dataframe.columns
    assert unification.manifest["extra_columns_dropped"] == []


def test_fail_validation_prevents_unification(contract_path: Path, fixtures_dir: Path):
    contract = load_input_contract(contract_path)
    validation_result = validate_csv_file(
        file_path=fixtures_dir / "rossmann_train_missing_required.csv",
        contract=contract,
        profile_name="rossmann_train",
    )

    assert validation_result.report["status"] == "FAIL"
    with pytest.raises(ValueError, match="Cannot unify dataset with FAIL validation status"):
        unify_validated_dataframe(
            validation_result=validation_result,
            contract=contract,
            profile_name="rossmann_train",
            source_file_name="rossmann_train_missing_required.csv",
        )
