from rezervo.chains.chain import Chain
from rezervo.providers.brpsystems.provider import BrpProvider
from rezervo.providers.schema import Branch, Location


class FscChain(Chain, BrpProvider):
    identifier = "fsc"
    name = "Family Sports Club"
    brp_subdomain = "fsc"
    branches = [
        Branch(
            identifier="ski",
            name="Ski",
            locations=[
                Location(identifier="ski", name="Ski", provider_identifier=8),
            ],
        ),
        Branch(
            identifier="bergen",
            name="Bergen",
            locations=[
                Location(
                    identifier="paradis", name="Paradis", provider_identifier=22206
                ),
                Location(identifier="askoy", name="Askøy", provider_identifier=5),
                Location(
                    identifier="danmarksplass",
                    name="Danmarksplass",
                    provider_identifier=10,
                ),
                Location(identifier="asane", name="Åsane", provider_identifier=4),
                Location(
                    identifier="kronstad", name="Kronstad", provider_identifier=23281
                ),
            ],
        ),
        Branch(
            identifier="alesund",
            name="Ålesund",
            locations=[
                Location(identifier="moa", name="Moa", provider_identifier=700),
                Location(
                    identifier="alesund",
                    name="Ålesund",
                    provider_identifier=701,
                ),
                Location(
                    identifier="ratvika", name="Ratvika", provider_identifier=23271
                ),
            ],
        ),
        Branch(
            identifier="arendal",
            name="Arendal",
            locations=[
                Location(
                    identifier="arendal", name="Arendal", provider_identifier=8381
                ),
            ],
        ),
        Branch(
            identifier="askim",
            name="Askim",
            locations=[
                Location(identifier="askim", name="Askim", provider_identifier=19730),
            ],
        ),
        Branch(
            identifier="averoy",
            name="Averøy",
            locations=[
                Location(identifier="averoy", name="Averøy", provider_identifier=21278),
            ],
        ),
        Branch(
            identifier="larvik",
            name="Larvik",
            locations=[
                Location(
                    identifier="langestrand",
                    name="Langestrand",
                    provider_identifier=8383,
                ),
                Location(
                    identifier="torstrand",
                    name="Torstrand",
                    provider_identifier=8384,
                ),
            ],
        ),
        Branch(
            identifier="drammen",
            name="Drammen",
            locations=[
                Location(
                    identifier="akropolis-assiden",
                    name="Akropolis Assiden",
                    provider_identifier=20901,
                ),
                Location(
                    identifier="akropolis-lier",
                    name="Akropolis Lier",
                    provider_identifier=20902,
                ),
                Location(
                    identifier="akropolis-marienlyst",
                    name="Akropolis Marienlyst",
                    provider_identifier=20903,
                ),
            ],
        ),
        Branch(
            identifier="city-nord",
            name="City Nord",
            locations=[
                Location(
                    identifier="city-nord", name="City Nord", provider_identifier=719
                ),
            ],
        ),
        Branch(
            identifier="drobak",
            name="Drøbak",
            locations=[
                Location(identifier="drobak", name="Drøbak", provider_identifier=11),
            ],
        ),
        Branch(
            identifier="fauske",
            name="Fauske",
            locations=[
                Location(identifier="fauske", name="Fauske", provider_identifier=723),
            ],
        ),
        Branch(
            identifier="finnsnes",
            name="Finnsnes",
            locations=[
                Location(
                    identifier="finnsnes", name="Finnsnes", provider_identifier=735
                ),
            ],
        ),
        Branch(
            identifier="harstad",
            name="Harstad",
            locations=[
                Location(identifier="harstad", name="Harstad", provider_identifier=730),
            ],
        ),
        Branch(
            identifier="grimstad",
            name="Grimstad",
            locations=[
                Location(
                    identifier="grimstad", name="Grimstad", provider_identifier=8382
                ),
            ],
        ),
        Branch(
            identifier="iseveien",
            name="Iseveien",
            locations=[
                Location(
                    identifier="iseveien", name="Iseveien", provider_identifier=19723
                ),
            ],
        ),
        Branch(
            identifier="jensvoll",
            name="Jensvoll",
            locations=[
                Location(
                    identifier="jensvoll", name="Jensvoll", provider_identifier=712
                ),
            ],
        ),
        Branch(
            identifier="key-norve",
            name="Key Nørve",
            locations=[
                Location(
                    identifier="key-norve", name="Key Nørve", provider_identifier=702
                ),
            ],
        ),
        Branch(
            identifier="kristiansund",
            name="Kristiansund",
            locations=[
                Location(
                    identifier="kristiansund",
                    name="Kristiansund",
                    provider_identifier=21277,
                ),
            ],
        ),
        Branch(
            identifier="mjondalen",
            name="Mjøndalen",
            locations=[
                Location(
                    identifier="mjondalen", name="Mjøndalen", provider_identifier=1
                ),
            ],
        ),
        Branch(
            identifier="mo-i-rana",
            name="Mo i Rana",
            locations=[
                Location(
                    identifier="mo-i-rana", name="Mo i Rana", provider_identifier=724
                ),
            ],
        ),
        Branch(
            identifier="morkved",
            name="Mørkved",
            locations=[
                Location(identifier="morkved", name="Mørkved", provider_identifier=716),
            ],
        ),
        Branch(
            identifier="orje",
            name="Ørje",
            locations=[
                Location(identifier="orje", name="Ørje", provider_identifier=19729),
            ],
        ),
        Branch(
            identifier="orsta",
            name="Ørsta",
            locations=[
                Location(identifier="orsta", name="Ørsta", provider_identifier=21926),
            ],
        ),
        Branch(
            identifier="porsgrunn",
            name="Porsgrunn",
            locations=[
                Location(
                    identifier="porsgrunn", name="Porsgrunn", provider_identifier=21181
                ),
            ],
        ),
        Branch(
            identifier="rakkestad",
            name="Rakkestad",
            locations=[
                Location(
                    identifier="rakkestad", name="Rakkestad", provider_identifier=19726
                ),
            ],
        ),
        Branch(
            identifier="rogan",
            name="Rogan",
            locations=[
                Location(identifier="rogan", name="Rogan", provider_identifier=721),
            ],
        ),
        Branch(
            identifier="skansegata",
            name="Skansegata",
            locations=[
                Location(
                    identifier="skansegata",
                    name="Skansegata",
                    provider_identifier=23270,
                ),
            ],
        ),
        Branch(
            identifier="skarnes",
            name="Skarnes",
            locations=[
                Location(
                    identifier="skarnes", name="Skarnes", provider_identifier=19727
                ),
            ],
        ),
        Branch(
            identifier="skien",
            name="Skien",
            locations=[
                Location(identifier="skien", name="Skien", provider_identifier=21162),
            ],
        ),
        Branch(
            identifier="sykkylven",
            name="Sykkylven",
            locations=[
                Location(
                    identifier="sykkylven", name="Sykkylven", provider_identifier=705
                ),
            ],
        ),
        Branch(
            identifier="sogne",
            name="Søgne",
            locations=[
                Location(identifier="sogne", name="Søgne", provider_identifier=19728),
            ],
        ),
        Branch(
            identifier="tonsberg",
            name="Tønsberg",
            locations=[
                Location(
                    identifier="tonsberg", name="Tønsberg", provider_identifier=8377
                ),
            ],
        ),
        Branch(
            identifier="vestby",
            name="Vestby",
            locations=[
                Location(identifier="vestby", name="Vestby", provider_identifier=9),
            ],
        ),
        Branch(
            identifier="volda",
            name="Volda",
            locations=[
                Location(identifier="volda", name="Volda", provider_identifier=704),
                Location(
                    identifier="voldahallen",
                    name="Voldahallen",
                    provider_identifier=21923,
                ),
            ],
        ),
    ]
