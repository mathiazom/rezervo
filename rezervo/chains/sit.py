from rezervo.chains.chain import Chain
from rezervo.chains.schema import (
    ChainProfileImages,
    ThemeAgnosticImages,
    ThemeSpecificImages,
)
from rezervo.providers.ibooking.provider import IBookingProvider
from rezervo.providers.schema import Branch, Location
from rezervo.utils.santa_utils import check_santa_time

is_santa_time = check_santa_time()


class SitChain(Chain, IBookingProvider):
    identifier = "sit"
    name = "Sit Trening"
    images = ChainProfileImages(
        light=ThemeSpecificImages(
            large_logo=f"images/chains/sit/light/logo_large{'_santa.png' if is_santa_time else '.svg'}"
        ),
        dark=ThemeSpecificImages(
            large_logo=f"images/chains/sit/dark/logo_large{'_santa.png' if is_santa_time else '.svg'}"
        ),
        common=ThemeAgnosticImages(
            small_logo=f"images/chains/sit/common/logo_small{'_santa' if is_santa_time else ''}.png"
        ),
    )
    ibooking_domain = "sit"
    branches = [
        Branch(
            identifier="trondheim",
            name="Trondheim",
            locations=[
                Location(
                    identifier="gloshaugen",
                    name="Gløshaugen",
                    provider_identifier=306,
                ),
                Location(
                    identifier="dragvoll", name="Dragvoll", provider_identifier=307
                ),
                Location(identifier="moholt", name="Moholt", provider_identifier=540),
                Location(identifier="dmmh", name="DMMH", provider_identifier=402),
                Location(
                    identifier="portalen", name="Portalen", provider_identifier=308
                ),
            ],
        ),
        Branch(
            identifier="gjovik",
            name="Gjøvik",
            locations=[
                Location(identifier="gjovik", name="Gjøvik", provider_identifier=968),
            ],
        ),
        Branch(
            identifier="alesund",
            name="Ålesund",
            locations=[
                Location(identifier="alesund", name="Ålesund", provider_identifier=863),
            ],
        ),
    ]
