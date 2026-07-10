from rezervo.chains.chain import Chain
from rezervo.chains.schema import (
    ChainProfileImages,
    ThemeAgnosticImages,
    ThemeSpecificImages,
)
from rezervo.providers.mirage.provider import MirageProvider
from rezervo.providers.schema import Branch, Location


class DotGymChain(Chain, MirageProvider):
    identifier = "dotgym"
    name = "DotGym"
    mirage_chain_identifier = identifier

    def images(self) -> ChainProfileImages:
        return ChainProfileImages(
            light=ThemeSpecificImages(
                large_logo="images/chains/dotgym/light/logo_large.png"
            ),
            dark=ThemeSpecificImages(
                large_logo="images/chains/dotgym/dark/logo_large.png"
            ),
            common=ThemeAgnosticImages(
                small_logo="images/chains/dotgym/common/logo_small.png"
            ),
        )

    branches = [
        Branch(
            identifier="trondheim",
            name="Trondheim",
            locations=[
                Location(
                    identifier="lil-siggy",
                    name="Lil Siggy",
                    provider_identifier="lil-siggy",
                ),
            ],
        ),
        Branch(
            identifier="ski",
            name="Ski",
            locations=[
                Location(
                    identifier="fratski",
                    name="Fratski",
                    provider_identifier="fratski",
                ),
            ],
        ),
    ]
