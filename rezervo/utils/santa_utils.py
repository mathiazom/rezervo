from datetime import datetime

from rezervo.consts import OSLO_TIMEZONE


def check_santa_time() -> bool:
    # TODO: clean this
    return datetime.now(OSLO_TIMEZONE).month == 12
