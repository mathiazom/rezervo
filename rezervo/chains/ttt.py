from rezervo.chains.chain import Chain
from rezervo.chains.schema import (
    ChainProfileImages,
    ThemeAgnosticImages,
    ThemeSpecificImages,
)
from rezervo.providers.brpsystems.provider import BrpProvider
from rezervo.providers.schema import Branch, Location
from rezervo.utils.santa_utils import check_santa_time

is_santa_time = check_santa_time()


class TttChain(Chain, BrpProvider):
    identifier = "3t"
    name = "3T"
    images = ChainProfileImages(
        light=ThemeSpecificImages(
            large_logo=f"images/chains/3t/light/logo_large{'_santa' if is_santa_time else ''}.png"
        ),
        dark=ThemeSpecificImages(
            large_logo=f"images/chains/3t/dark/logo_large{'_santa' if is_santa_time else ''}.png"
        ),
        common=ThemeAgnosticImages(
            small_logo=f"images/chains/3t/common/logo_small{'_santa' if is_santa_time else ''}.png"
        ),
    )
    brp_subdomain = "3t"
    branches = [
        Branch(
            identifier="trondheim",
            name="Trondheim",
            locations=[
                Location(identifier="byasen", name="Byåsen", provider_identifier=10),
                Location(
                    identifier="fossegrenda",
                    name="Fossegrenda",
                    provider_identifier=5860,
                ),
                Location(
                    identifier="ilsvika", name="Ilsvika", provider_identifier=5587
                ),
                Location(identifier="leangen", name="Leangen", provider_identifier=2),
                Location(identifier="midtbyen", name="Midtbyen", provider_identifier=3),
                Location(identifier="moholt", name="Moholt", provider_identifier=5588),
                Location(
                    identifier="ranheim", name="Ranheim", provider_identifier=5819
                ),
                Location(identifier="rosten", name="Rosten", provider_identifier=1),
                Location(identifier="saupstad", name="Saupstad", provider_identifier=4),
                Location(identifier="sluppen", name="Sluppen", provider_identifier=6),
                Location(
                    identifier="solsiden", name="Solsiden", provider_identifier=4542
                ),
                Location(
                    identifier="cageball-rosten",
                    name="Cageball Rosten",
                    provider_identifier=4812,
                ),
                Location(
                    identifier="crossfit-moholt",
                    name="Crossfit Moholt",
                    provider_identifier=6667,
                ),
            ],
        ),
        Branch(
            identifier="levanger",
            name="Levanger",
            locations=[
                Location(identifier="levanger", name="Levanger", provider_identifier=7),
            ],
        ),
        Branch(
            identifier="melhus",
            name="Melhus",
            locations=[
                Location(identifier="melhus", name="Melhus", provider_identifier=5820),
            ],
        ),
        Branch(
            identifier="orkanger",
            name="Orkanger",
            locations=[
                Location(identifier="orkanger", name="Orkanger", provider_identifier=8),
            ],
        ),
        Branch(
            identifier="steinkjer",
            name="Steinkjer",
            locations=[
                Location(
                    identifier="steinkjer", name="Steinkjer", provider_identifier=5
                ),
            ],
        ),
        Branch(
            identifier="stjordal",
            name="Stjørdal",
            locations=[
                Location(
                    identifier="stjordal", name="Stjørdal", provider_identifier=6247
                ),
            ],
        ),
    ]
