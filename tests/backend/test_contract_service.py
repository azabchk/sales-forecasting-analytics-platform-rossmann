from __future__ import annotations

import os
import sys
from pathlib import Path

import yaml

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from backend.app.services.contract_service import (  # noqa: E402
    get_contract,
    get_contract_version,
    list_contracts,
    list_contract_versions,
)


def test_contract_registry_parsing_and_schema_summary(tmp_path: Path):
    registry_path = tmp_path / "contracts_registry.yaml"
    payload = {
        "version": "v1",
        "contracts": [
            {
                "id": "rossmann_input_contract",
                "name": "Rossmann Input Contract",
                "description": "Test contract",
                "is_active": True,
                "versions": [
                    {
                        "version": "v1",
                        "created_at": "2026-01-01T00:00:00Z",
                        "changed_by": "qa",
                        "changelog": "initial",
                        "schema_path": "config/input_contract/contract_v1.yaml",
                    }
                ],
            }
        ],
    }
    registry_path.write_text(yaml.safe_dump(payload, sort_keys=False), encoding="utf-8")

    previous = os.environ.get("CONTRACTS_REGISTRY_PATH")
    os.environ["CONTRACTS_REGISTRY_PATH"] = str(registry_path)
    try:
        contracts = list_contracts()
        assert len(contracts) == 1
        assert contracts[0]["latest_version"] == "v1"

        contract = get_contract("rossmann_input_contract")
        assert contract is not None
        assert contract["name"] == "Rossmann Input Contract"

        versions = list_contract_versions("rossmann_input_contract")
        assert len(versions) == 1
        assert versions[0]["version"] == "v1"

        version_detail = get_contract_version("rossmann_input_contract", "v1")
        assert version_detail is not None
        assert "profiles" in version_detail
        train_profile = version_detail["profiles"]["rossmann_train"]
        assert "store_id" in train_profile["required_columns"]
        assert "sales" in train_profile["dtypes"]
    finally:
        if previous is None:
            os.environ.pop("CONTRACTS_REGISTRY_PATH", None)
        else:
            os.environ["CONTRACTS_REGISTRY_PATH"] = previous
