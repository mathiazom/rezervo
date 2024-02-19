from rezervo.chains.chain import Chain
from rezervo.providers.sats.provider import SatsProvider
from rezervo.providers.schema import Branch, Location


class SatsChain(Chain, SatsProvider):
    identifier = "sats"
    name = "Sats"
    branches = [
        Branch(
            identifier="oslo/akershus",
            name="Oslo/Akershus",
            locations=[
                Location(identifier="kolbotn", name="Kolbotn", provider_identifier=224),
                Location(identifier="ryen", name="Ryen", provider_identifier=219),
            ],
        ),
    ]
