from fastapi import APIRouter, HTTPException

from rezervo.chains.active import ACTIVE_CHAIN_IDENTIFIERS
from rezervo.chains.common import find_class_by_id
from rezervo.schemas.config.user import ChainIdentifier
from rezervo.schemas.schedule import RezervoClass

router = APIRouter()


@router.get("/classes/{chain_identifier}/{class_id}")
async def get_chain_class_by_id(chain_identifier: ChainIdentifier, class_id: str):
    if chain_identifier not in ACTIVE_CHAIN_IDENTIFIERS:
        raise HTTPException(
            status_code=404, detail=f"Chain '{chain_identifier}' not recognized."
        )
    res = await find_class_by_id(chain_identifier, class_id)
    if isinstance(res, RezervoClass):
        return res
    raise HTTPException(status_code=404, detail="Class not found.")
