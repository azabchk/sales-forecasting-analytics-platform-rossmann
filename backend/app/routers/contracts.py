from __future__ import annotations

from fastapi import APIRouter, HTTPException

from app.schemas import (
    ContractDetailResponse,
    ContractSummaryResponse,
    ContractVersionDetailResponse,
    ContractVersionSummaryResponse,
)
from app.services.contract_service import (
    get_contract,
    get_contract_version,
    list_contract_versions,
    list_contracts,
)

router = APIRouter()


@router.get("/contracts", response_model=list[ContractSummaryResponse])
def get_contract_list() -> list[ContractSummaryResponse]:
    try:
        rows = list_contracts()
        return [ContractSummaryResponse.model_validate(row) for row in rows]
    except (FileNotFoundError, ValueError) as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@router.get("/contracts/{contract_id}", response_model=ContractDetailResponse)
def get_contract_by_id(contract_id: str) -> ContractDetailResponse:
    try:
        row = get_contract(contract_id)
        if row is None:
            raise HTTPException(status_code=404, detail=f"Contract not found: {contract_id}")
        return ContractDetailResponse.model_validate(row)
    except HTTPException:
        raise
    except (FileNotFoundError, ValueError) as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@router.get("/contracts/{contract_id}/versions", response_model=list[ContractVersionSummaryResponse])
def get_contract_versions(contract_id: str) -> list[ContractVersionSummaryResponse]:
    try:
        contract = get_contract(contract_id)
        if contract is None:
            raise HTTPException(status_code=404, detail=f"Contract not found: {contract_id}")
        rows = list_contract_versions(contract_id)
        return [ContractVersionSummaryResponse.model_validate(row) for row in rows]
    except HTTPException:
        raise
    except (FileNotFoundError, ValueError) as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@router.get(
    "/contracts/{contract_id}/versions/{version}",
    response_model=ContractVersionDetailResponse,
)
def get_contract_version_by_id(contract_id: str, version: str) -> ContractVersionDetailResponse:
    try:
        row = get_contract_version(contract_id, version)
        if row is None:
            raise HTTPException(status_code=404, detail=f"Contract version not found: {contract_id}/{version}")
        return ContractVersionDetailResponse.model_validate(row)
    except HTTPException:
        raise
    except (FileNotFoundError, ValueError) as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc
