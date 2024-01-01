from rezervo.chains.chain import Chain
from rezervo.providers.ibooking.provider import IBookingProvider
from rezervo.providers.schema import Branch, Location


class SitChain(Chain, IBookingProvider):
    identifier = "sit"
    name = "Sit Trening"
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
