from fastapi import APIRouter, HTTPException, Query
from typing_extensions import Annotated

from rezervo.chains.active import ACTIVE_CHAIN_IDENTIFIERS, get_chain
from rezervo.chains.common import fetch_week_schedule
from rezervo.providers.schema import BranchIdentifier, LocationIdentifier
from rezervo.schemas.config.user import ChainIdentifier
from rezervo.schemas.schedule import RezervoSchedule

router = APIRouter()


@router.get("/schedule/{chain_identifier}/{week_offset}")
def get_branch_week_schedule(
    chain_identifier: ChainIdentifier,
    week_offset: int,
    branches: Annotated[
        list[BranchIdentifier] | None, Query(alias="branch")
    ] = None,  # TODO: consider removing branches parameter
    locations: Annotated[
        list[LocationIdentifier] | None, Query(alias="location")
    ] = None,
) -> RezervoSchedule:
    if chain_identifier not in ACTIVE_CHAIN_IDENTIFIERS:
        raise HTTPException(
            status_code=404, detail=f"Chain '{chain_identifier}' not recognized."
        )
    chain = get_chain(chain_identifier)
    if branches is not None:
        chain_branches = [branch.identifier for branch in chain.branches]
        for branch in branches:
            if branch not in chain_branches:
                raise HTTPException(
                    status_code=404, detail=f"Branch '{branch}' not recognized."
                )
    if locations is not None:
        chain_location_identifiers = [
            location.identifier  # TODO: verify type
            for branch in chain.branches
            for location in branch.locations
        ]
        for location in locations:
            if location not in chain_location_identifiers:
                raise HTTPException(
                    status_code=404, detail=f"Location '{location}' not recognized."
                )
    return fetch_week_schedule(
        chain_identifier, week_offset, branches=branches, locations=locations
    )
