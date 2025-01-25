from rezervo.chains.chain import Chain
from rezervo.chains.ttt import TttChain
from rezervo.schemas.config.user import ChainIdentifier

ACTIVE_CHAINS: list[Chain] = [TttChain()]

ACTIVE_CHAIN_IDENTIFIERS = [c.identifier for c in ACTIVE_CHAINS]


def get_chain(chain_identifier: ChainIdentifier) -> Chain:
    for c in ACTIVE_CHAINS:
        if c.identifier == chain_identifier:
            return c
    raise ValueError(f"Chain {chain_identifier} is not active.")
