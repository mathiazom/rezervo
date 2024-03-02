from fastapi import APIRouter, HTTPException

from rezervo.chains.active import ACTIVE_CHAIN_IDENTIFIERS, ACTIVE_CHAINS, get_chain
from rezervo.chains.schema import ChainResponse, ChainProfile
from rezervo.schemas.config.user import ChainIdentifier

router = APIRouter()


@router.get("/chains", response_model=list[ChainResponse])
def get_chains():
    return [
        ChainResponse(
            profile=ChainProfile(
                identifier=chain.identifier,
                name=chain.name,
                images=chain.images,
            ),
            branches=chain.branches,
        )
        for chain in ACTIVE_CHAINS
    ]


@router.get("/chains/{chain_identifier}", response_model=ChainResponse)
def get_chain_by_identifier(
    chain_identifier: ChainIdentifier,
):
    if chain_identifier not in ACTIVE_CHAIN_IDENTIFIERS:
        raise HTTPException(
            status_code=404, detail=f"Chain '{chain_identifier}' not recognized."
        )
    chain = get_chain(chain_identifier)
    return ChainResponse(
        profile=ChainProfile(
            identifier=chain.identifier,
            name=chain.name,
            images=chain.images,
        ),
        branches=chain.branches,
    )
