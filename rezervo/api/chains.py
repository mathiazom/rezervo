from fastapi import APIRouter, HTTPException

from rezervo.chains.active import ACTIVE_CHAIN_IDENTIFIERS, ACTIVE_CHAINS, get_chain
from rezervo.chains.schema import BranchProfile, ChainProfile, ChainResponse
from rezervo.schemas.config.user import ChainIdentifier

router = APIRouter()


def chain_response_from_chain(chain):
    return ChainResponse(
        profile=ChainProfile(
            identifier=chain.identifier,
            name=chain.name,
            images=chain.images,
        ),
        branches=[
            BranchProfile(
                identifier=branch.identifier,
                name=branch.name,
                locations=branch.locations,
            )
            for branch in chain.branches
        ],
    )


@router.get("/chains", response_model=list[ChainResponse])
def get_chains():
    return [chain_response_from_chain(chain) for chain in ACTIVE_CHAINS]


@router.get("/chains/{chain_identifier}", response_model=ChainResponse)
def get_chain_by_identifier(
    chain_identifier: ChainIdentifier,
):
    if chain_identifier not in ACTIVE_CHAIN_IDENTIFIERS:
        raise HTTPException(
            status_code=404, detail=f"Chain '{chain_identifier}' not recognized."
        )
    return chain_response_from_chain(get_chain(chain_identifier))
