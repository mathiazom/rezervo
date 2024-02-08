from typing import Optional

from pydantic.main import BaseModel


class RezervoBaseCategory(BaseModel):
    name: str
    color: str


class RezervoCategory(RezervoBaseCategory):
    keywords: list[str]


OTHER_ACTIVITY_CATEGORY = RezervoCategory(
    name="Annet",
    color="#FFFF66",
    keywords=["happening", "event"],
)

ACTIVITY_CATEGORIES = [
    OTHER_ACTIVITY_CATEGORY,
    RezervoCategory(
        name="Tilleggstjenester",
        color="#f4eded",
        keywords=["tilleggstjenester", "barnepass", "kroppsanalyse"],
    ),
    RezervoCategory(
        name="Vannaerobic",
        color="#0047ab",
        keywords=["vann", "aqua", "svøm", "basseng"],
    ),
    RezervoCategory(
        name="Mosjon",
        color="#00B050",
        keywords=["mosjon", "godt voksen", "mamma", "mor og barn", "senior", "baby"],
    ),
    RezervoCategory(
        name="Dans",
        color="#E96179",
        keywords=["dans", "dance", "sh'bam", "zumba", "beatz", "rytmer", "bodyjam"],
    ),
    RezervoCategory(
        name="Body & Mind",
        color="#8BD4F0",
        keywords=[
            "body & mind",
            "yoga",
            "pilates",
            "smidig",
            "stretch",
            "mobilitet",
            "meditate",
            "flow",
            "yin",
            "soul",
            "breath",
            "grounding",
            "bodybalance",
            "ashtanga",
            "shapes",
        ],
    ),
    RezervoCategory(
        name="Spinning",
        color="#4C2C7E",
        keywords=["spin", "sykkel", "ride", "rpm"],
    ),
    RezervoCategory(
        name="Kondisjon",
        color="#6AD3B4",
        keywords=[
            "kondis",
            "step",
            "løp",
            "puls",
            "bodyattack",
            "cardio",
            "tredemølle",
            "hiit",
            "aerobic",
            "run",
            "combat",
        ],
    ),
    RezervoCategory(
        name="Styrke & Utholdenhet",
        color="#F8A800",
        keywords=[
            "utholdenhet",
            "pump",
            "styrke",
            "core",
            "sterk",
            "tabata",
            "stærk",
            "strength",
            "hardhausen",
            "slynge",
            "cross",
            "wod",
            "bodycross",
            "mrl",
            "sirkeltrening",
            "gjennomtrent",
            "rumpe",
            "booty",
            "bootcamp",
            "olympia",
        ],
    ),
]


def determine_activity_category(
    activity_name: str, has_additional_information: Optional[bool] = False
) -> RezervoCategory:
    if has_additional_information:
        return OTHER_ACTIVITY_CATEGORY
    for category in ACTIVITY_CATEGORIES:
        for keyword in category.keywords:
            if keyword in activity_name.lower():
                return category
    return OTHER_ACTIVITY_CATEGORY
