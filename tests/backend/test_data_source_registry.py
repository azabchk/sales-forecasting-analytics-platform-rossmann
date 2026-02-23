from __future__ import annotations

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.etl.data_source_registry import (  # noqa: E402
    create_data_source,
    list_data_sources,
    resolve_data_source_id,
)


def _sqlite_url(tmp_path: Path, name: str) -> str:
    return f"sqlite+pysqlite:///{(tmp_path / name).resolve()}"


def test_data_source_default_creation_and_list(tmp_path: Path):
    db_url = _sqlite_url(tmp_path, "data_source_default.db")
    rows = list_data_sources(database_url=db_url)

    assert len(rows) == 1
    assert rows[0]["name"] == "Rossmann Default"
    assert rows[0]["is_default"] is True
    assert resolve_data_source_id(None, database_url=db_url) == int(rows[0]["id"])


def test_data_source_create_and_resolve(tmp_path: Path):
    db_url = _sqlite_url(tmp_path, "data_source_create.db")

    created = create_data_source(
        name="Client A",
        description="Retail ERP connector",
        source_type="erp",
        related_contract_id="rossmann_input_contract",
        related_contract_version="v1",
        is_default=False,
        database_url=db_url,
    )

    assert created["name"] == "Client A"
    assert created["source_type"] == "erp"

    rows = list_data_sources(database_url=db_url)
    names = [row["name"] for row in rows]
    assert "Rossmann Default" in names
    assert "Client A" in names

    resolved = resolve_data_source_id(int(created["id"]), database_url=db_url)
    assert resolved == int(created["id"])
