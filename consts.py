from pathlib import Path

# Absolute normalized path to the root directory of the app
APP_ROOT = Path(__file__).parent.resolve()

WEEKDAYS = ["Mandag", "Tirsdag", "Onsdag", "Torsdag", "Fredag", "Lørdag", "Søndag"]

AUTH_URL = "https://www.sit.no/"

BOOKING_TIMEZONE = "Europe/Oslo"

MAX_BOOKING_ATTEMPTS = 10

CONFIG_PATH = "config.yaml"
