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


@pytest.fixture(scope="module")
def contract_path() -> Path:
    return PROJECT_ROOT / "config" / "input_contract" / "contract_v1.yaml"


@pytest.fixture(scope="module")
def fixtures_dir() -> Path:
    return PROJECT_ROOT / "tests" / "fixtures" / "input_samples"


def test_valid_file_pass(contract_path: Path, fixtures_dir: Path):
    contract = load_input_contract(contract_path)
    result = validate_csv_file(
        file_path=fixtures_dir / "rossmann_train_valid.csv",
        contract=contract,
        profile_name="rossmann_train",
    )

    assert result.report["status"] == "PASS"
    assert result.report["checks"]["required_columns"] == "PASS"
    assert result.dataframe is not None


def test_missing_required_columns_fail(contract_path: Path, fixtures_dir: Path):
    contract = load_input_contract(contract_path)
    result = validate_csv_file(
        file_path=fixtures_dir / "rossmann_train_missing_required.csv",
        contract=contract,
        profile_name="rossmann_train",
    )

    assert result.report["status"] == "FAIL"
    assert result.report["checks"]["required_columns"] == "FAIL"
    assert any("Missing required columns" in message for message in result.report["errors"])


def test_extra_columns_warn(contract_path: Path, fixtures_dir: Path):
    contract = load_input_contract(contract_path)
    result = validate_csv_file(
        file_path=fixtures_dir / "rossmann_train_extra_columns.csv",
        contract=contract,
        profile_name="rossmann_train",
    )

    assert result.report["status"] == "WARN"
    assert result.report["checks"]["extra_columns"] == "WARN"
    assert any("Extra columns detected" in message for message in result.report["warnings"])


def test_type_mismatch_warn_when_not_strict(contract_path: Path, fixtures_dir: Path):
    contract = load_input_contract(contract_path)
    contract.strict_types = False

    result = validate_csv_file(
        file_path=fixtures_dir / "rossmann_train_bad_types.csv",
        contract=contract,
        profile_name="rossmann_train",
    )

    assert result.report["status"] == "WARN"
    assert result.report["checks"]["types"] == "WARN"


def test_type_mismatch_fail_when_strict(contract_path: Path, fixtures_dir: Path):
    contract = load_input_contract(contract_path)
    contract.strict_types = True

    result = validate_csv_file(
        file_path=fixtures_dir / "rossmann_train_bad_types.csv",
        contract=contract,
        profile_name="rossmann_train",
    )

    assert result.report["status"] == "FAIL"
    assert result.report["checks"]["types"] == "FAIL"


def test_empty_file_fails(contract_path: Path, fixtures_dir: Path):
    contract = load_input_contract(contract_path)
    result = validate_csv_file(
        file_path=fixtures_dir / "rossmann_train_empty.csv",
        contract=contract,
        profile_name="rossmann_train",
    )

    assert result.report["status"] == "FAIL"
    assert any("empty" in message.lower() for message in result.report["errors"])


def test_unsupported_extension_fails(contract_path: Path, fixtures_dir: Path):
    contract = load_input_contract(contract_path)
    result = validate_csv_file(
        file_path=fixtures_dir / "not_csv.txt",
        contract=contract,
        profile_name="rossmann_train",
    )

    assert result.report["status"] == "FAIL"
    assert result.report["checks"]["format"] == "FAIL"


def test_alias_mapping_to_canonical_columns(contract_path: Path, fixtures_dir: Path):
    contract = load_input_contract(contract_path)
    result = validate_csv_file(
        file_path=fixtures_dir / "rossmann_train_valid.csv",
        contract=contract,
        profile_name="rossmann_train",
    )

    assert result.dataframe is not None
    expected_columns = {"store_id", "day_of_week", "full_date", "sales"}
    assert expected_columns.issubset(set(result.dataframe.columns))
