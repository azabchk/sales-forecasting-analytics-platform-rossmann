from __future__ import annotations

import sys
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from etl.etl_load import ETLConfig, run_preflight_hook
from src.etl.preflight_registry import get_latest_preflight


@pytest.fixture(scope="module")
def fixtures_dir() -> Path:
    return PROJECT_ROOT / "tests" / "fixtures" / "input_samples"


@pytest.fixture(scope="module")
def contract_path() -> Path:
    return PROJECT_ROOT / "config" / "input_contract" / "contract_v1.yaml"


def _make_cfg(
    *,
    train_csv: Path,
    store_csv: Path,
    contract_path: Path,
    artifact_dir: Path,
    mode: str,
) -> ETLConfig:
    return ETLConfig(
        train_csv=str(train_csv.resolve()),
        store_csv=str(store_csv.resolve()),
        db_url="postgresql+psycopg2://unused:unused@localhost:5432/unused",
        truncate_reload=False,
        chunksize=1000,
        preflight_mode=mode,
        preflight_profile_train="rossmann_train",
        preflight_profile_store="rossmann_store",
        preflight_contract_path=str(contract_path.resolve()),
        preflight_artifact_dir=str(artifact_dir.resolve()),
    )


def test_preflight_off_keeps_current_behavior(fixtures_dir: Path, contract_path: Path, tmp_path: Path):
    cfg = _make_cfg(
        train_csv=fixtures_dir / "rossmann_train_alias_mixed.csv",
        store_csv=fixtures_dir / "rossmann_store_valid.csv",
        contract_path=contract_path,
        artifact_dir=tmp_path / "preflight_artifacts",
        mode="off",
    )

    train_input, store_input, results = run_preflight_hook(cfg)

    assert train_input == cfg.train_csv
    assert store_input == cfg.store_csv
    assert results == {}


def test_preflight_report_only_generates_artifacts_but_uses_raw_file(
    fixtures_dir: Path,
    contract_path: Path,
    tmp_path: Path,
):
    cfg = _make_cfg(
        train_csv=fixtures_dir / "rossmann_train_semantic_warn.csv",
        store_csv=fixtures_dir / "rossmann_store_valid.csv",
        contract_path=contract_path,
        artifact_dir=tmp_path / "preflight_artifacts",
        mode="report_only",
    )

    train_input, store_input, results = run_preflight_hook(cfg)

    assert train_input == cfg.train_csv
    assert store_input == cfg.store_csv
    assert "train" in results and "store" in results

    train_result = results["train"]
    assert train_result.validation_status == "PASS"
    assert train_result.semantic_status == "WARN"
    assert train_result.validation_report_path is not None
    assert train_result.semantic_report_path is not None
    assert train_result.unification_manifest_path is not None
    assert train_result.unified_output_path is not None
    assert Path(train_result.validation_report_path).exists()
    assert Path(train_result.semantic_report_path).exists()
    assert Path(train_result.unification_manifest_path).exists()
    assert Path(train_result.unified_output_path).exists()
    assert train_result.preflight_report_path is not None
    assert Path(train_result.preflight_report_path).exists()


def test_preflight_enforce_fail_blocks_etl(fixtures_dir: Path, contract_path: Path, tmp_path: Path):
    cfg = _make_cfg(
        train_csv=fixtures_dir / "rossmann_train_missing_required.csv",
        store_csv=fixtures_dir / "rossmann_store_valid.csv",
        contract_path=contract_path,
        artifact_dir=tmp_path / "preflight_artifacts",
        mode="enforce",
    )

    with pytest.raises(ValueError, match="Preflight blocked ETL"):
        run_preflight_hook(cfg)


def test_preflight_enforce_warn_uses_unified_file(fixtures_dir: Path, contract_path: Path, tmp_path: Path):
    cfg = _make_cfg(
        train_csv=fixtures_dir / "rossmann_train_extra_columns.csv",
        store_csv=fixtures_dir / "rossmann_store_valid.csv",
        contract_path=contract_path,
        artifact_dir=tmp_path / "preflight_artifacts",
        mode="enforce",
    )

    train_input, store_input, results = run_preflight_hook(cfg)

    assert "train" in results and "store" in results
    assert results["train"].validation_status == "WARN"
    assert results["train"].semantic_status == "PASS"
    assert train_input != cfg.train_csv
    assert store_input != cfg.store_csv
    assert train_input == results["train"].unified_output_path
    assert store_input == results["store"].unified_output_path
    assert Path(train_input).exists()
    assert Path(store_input).exists()


def test_preflight_enforce_semantic_fail_blocks_etl(fixtures_dir: Path, contract_path: Path, tmp_path: Path):
    cfg = _make_cfg(
        train_csv=fixtures_dir / "rossmann_train_semantic_fail_sales.csv",
        store_csv=fixtures_dir / "rossmann_store_valid.csv",
        contract_path=contract_path,
        artifact_dir=tmp_path / "preflight_artifacts",
        mode="enforce",
    )

    with pytest.raises(ValueError, match="Preflight blocked ETL"):
        run_preflight_hook(cfg)


def test_preflight_enforce_fail_persisted_and_visible(fixtures_dir: Path, contract_path: Path, tmp_path: Path, monkeypatch):
    registry_db = tmp_path / "preflight_registry_visibility.db"
    database_url = f"sqlite+pysqlite:///{registry_db.resolve()}"
    monkeypatch.setenv("DATABASE_URL", database_url)

    cfg = _make_cfg(
        train_csv=fixtures_dir / "rossmann_train_semantic_fail_sales.csv",
        store_csv=fixtures_dir / "rossmann_store_valid.csv",
        contract_path=contract_path,
        artifact_dir=tmp_path / "preflight_artifacts",
        mode="enforce",
    )

    with pytest.raises(ValueError, match="Preflight blocked ETL"):
        run_preflight_hook(cfg)

    latest = get_latest_preflight(source_name="train", database_url=database_url)
    assert latest is not None
    assert latest["blocked"] is True
    assert latest["final_status"] == "FAIL"
    assert latest["block_reason"] == "semantic_fail"
