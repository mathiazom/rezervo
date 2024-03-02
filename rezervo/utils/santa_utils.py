from datetime import datetime

import pytz


def check_santa_time() -> bool:
    # TODO: clean this
    return datetime.now(pytz.timezone("Europe/Oslo")).month == 12
