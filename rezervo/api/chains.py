from fastapi import APIRouter
from pydantic.main import BaseModel

from rezervo.chains.active import ACTIVE_CHAINS
from rezervo.providers.schema import BaseBranch, BaseLocation

router = APIRouter()


class BranchProfile(BaseBranch):
    locations: list[BaseLocation]


class ChainProfile(BaseModel):
    identifier: str
    name: str


class ChainResponse(BaseModel):
    profile: ChainProfile
    branches: list[BranchProfile]


@router.get("/chains", response_model=list[ChainResponse])
def get_chains():
    return [
        ChainResponse(
            profile=ChainProfile(
                identifier=chain.identifier,
                name=chain.name,
            ),
            branches=chain.branches,
        )
        for chain in ACTIVE_CHAINS
    ]
