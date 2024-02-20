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
                Location(
                    identifier="akersgata", name="Akersgata", provider_identifier=166
                ),
                Location(identifier="asker", name="Asker", provider_identifier=206),
                Location(identifier="bislett", name="Bislett", provider_identifier=156),
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
            identifier="drammen",
            name="Drammen",
            locations=[
                Location(identifier="drammen", name="Drammen", provider_identifier=106),
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
        Branch(
            identifier="tromsø",
            name="Tromsø",
            locations=[
                Location(identifier="langnes", name="Langnes", provider_identifier=154),
                Location(identifier="tromsø", name="Tromsø", provider_identifier=142),
            ],
        ),
    ]
