from fastapi import APIRouter, HTTPException, Query
from typing_extensions import Annotated

from rezervo.chains.active import ACTIVE_CHAIN_IDENTIFIERS, get_chain
from rezervo.chains.common import fetch_week_schedule
from rezervo.providers.schema import LocationIdentifier
from rezervo.schemas.config.user import ChainIdentifier
from rezervo.schemas.schedule import RezervoSchedule

router = APIRouter()


@router.get("/schedule/{chain_identifier}/{compact_iso_week}")
async def get_chain_week_schedule(
    chain_identifier: ChainIdentifier,
    compact_iso_week: str,
    locations: Annotated[
        list[LocationIdentifier] | None, Query(alias="location")
    ] = None,
) -> RezervoSchedule:
    if chain_identifier not in ACTIVE_CHAIN_IDENTIFIERS:
        raise HTTPException(
            status_code=404, detail=f"Chain '{chain_identifier}' not recognized."
        )
    if locations is None:
        locations = []
    chain = get_chain(chain_identifier)
    chain_locations = chain.locations()
    for location in locations:
        if location not in chain_locations:
            raise HTTPException(
                status_code=404, detail=f"Location '{location}' not recognized."
            )
    return await fetch_week_schedule(chain_identifier, compact_iso_week, locations)
