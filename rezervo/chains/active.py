from rezervo.chains.chain import Chain
from rezervo.chains.dotgym import DotGymChain
from rezervo.chains.sats import SatsChain
from rezervo.chains.sporty import SportyChain
from rezervo.chains.ttt import TttChain
from rezervo.providers.mirage.settings import get_mirage_settings
from rezervo.schemas.config.user import ChainIdentifier

ACTIVE_CHAINS: list[Chain] = [SportyChain(), TttChain(), SatsChain()]

if get_mirage_settings().enabled:
    ACTIVE_CHAINS.append(DotGymChain())

ACTIVE_CHAIN_IDENTIFIERS = [c.identifier for c in ACTIVE_CHAINS]


def get_chain(chain_identifier: ChainIdentifier) -> Chain:
    for c in ACTIVE_CHAINS:
        if c.identifier == chain_identifier:
            return c
    raise ValueError(f"Chain {chain_identifier} is not active.")
