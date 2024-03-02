from datetime import datetime


def check_santa_time() -> bool:
    return datetime.now().month == 12
