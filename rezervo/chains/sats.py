from rezervo.chains.chain import Chain
from rezervo.chains.schema import (
    ChainProfileImages,
    ThemeAgnosticImages,
    ThemeSpecificImages,
)
from rezervo.providers.sats.provider import SatsProvider
from rezervo.providers.schema import Branch, Location
from rezervo.utils.santa_utils import check_santa_time

is_santa_time = check_santa_time()


class SatsChain(Chain, SatsProvider):
    identifier = "sats"
    name = "Sats"
    images = ChainProfileImages(
        light=ThemeSpecificImages(
            large_logo=f"images/chains/sats/light/logo_large{'_santa' if is_santa_time else ''}.png"
        ),
        dark=ThemeSpecificImages(
            large_logo=f"images/chains/sats/dark/logo_large{'_santa' if is_santa_time else ''}.png"
        ),
        common=ThemeAgnosticImages(
            small_logo=f"images/chains/sats/common/logo_small{'_santa' if is_santa_time else ''}.png"
        ),
    )
    branches = [
        Branch(
            identifier="oslo/akershus",
            name="Oslo/Akershus",
            locations=[
                Location(identifier="kolbotn", name="Kolbotn", provider_identifier=224),
                Location(identifier="ryen", name="Ryen", provider_identifier=219),
                Location(
                    identifier="akersgata", name="Akersgata", provider_identifier=166
                ),
                Location(identifier="asker", name="Asker", provider_identifier=206),
                Location(identifier="bislett", name="Bislett", provider_identifier=156),
                Location(
                    identifier="bjorvika", name="Bjørvika", provider_identifier=208
                ),
                Location(
                    identifier="ringnes-park",
                    name="Ringnes Park",
                    provider_identifier=218,
                ),
                Location(
                    identifier="aker-brygge",
                    name="Aker Brygge",
                    provider_identifier=802,
                ),
            ],
        ),
        Branch(
            identifier="bergen",
            name="Bergen",
            locations=[
                Location(identifier="bergen", name="Bergen", provider_identifier=114),
                Location(
                    identifier="damsgård", name="Damsgård", provider_identifier=231
                ),
                Location(identifier="lagunen", name="Lagunen", provider_identifier=187),
            ],
        ),
        Branch(
            identifier="rogaland",
            name="Rogaland",
            locations=[
                Location(identifier="bryne", name="Bryne", provider_identifier=232),
                Location(identifier="sandnes", name="Sandnes", provider_identifier=171),
                Location(identifier="hinna", name="Hinna", provider_identifier=267),
            ],
        ),
    ]
