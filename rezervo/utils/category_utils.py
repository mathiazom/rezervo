from pydantic.main import BaseModel


class RezervoBaseCategory(BaseModel):
    name: str
    color: str


class RezervoCategory(RezervoBaseCategory):
    keywords: list[str]


OTHER_ACTIVITY_CATEGORY = RezervoCategory(
    name="Annet",
    color="#FFEE00",
    keywords=["happening", "event"],
)

ACTIVITY_CATEGORIES = [
    OTHER_ACTIVITY_CATEGORY,
    RezervoCategory(
        name="Tilleggstjenester",
        color="#CFCFCF",
        keywords=["tilleggstjenester", "barnepass", "kroppsanalyse"],
    ),
    RezervoCategory(
        name="Vannaerobic",
        color="#0047ab",
        keywords=["vann", "aqua", "svøm", "basseng"],
    ),
    RezervoCategory(
        name="Mosjon",
        color="#00A050",
        keywords=[
            "mosjon",
            "godt voksen",
            "mamma",
            "mor og barn",
            "senior",
            "baby",
            "mama",
            "familie",
            "kids",
            "sprek",
            "walk",
        ],
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
            "shape",
            "flexibility",
            "balance",
        ],
    ),
    RezervoCategory(
        name="Spinning",
        color="#4C2C7E",
        keywords=["spin", "sykkel", "ride", "rpm", "cycling"],
    ),
    RezervoCategory(
        name="Kondisjon",
        color="#C040A0",
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
            "prformance",
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
            "absolution",
            "bodyweight",
            "x-fit",
            "kettlebell",
            "skill athletic",
            "sirkel",
        ],
    ),
]


def determine_activity_category(activity_name: str) -> RezervoCategory:
    for category in ACTIVITY_CATEGORIES:
        for keyword in category.keywords:
            if keyword in activity_name.lower():
                return category
    return OTHER_ACTIVITY_CATEGORY
