import datetime


def readable_seconds(s: float):
    minutes = int(s / 60)
    seconds = int(s % 60)
    return "".join(
        [
            f"{minutes} minute{'s' if minutes > 1 else ''}{' and ' if seconds > 0 else ''}"
            if minutes > 0
            else "",
            f"{seconds} second{'s' if seconds > 1 else ''}" if seconds > 0 else "",
        ]
    )


def total_days_for_next_whole_weeks(weeks: int):
    # number of days left of the current week plus days in `weeks` number of whole weeks
    return (7 - datetime.datetime.now().weekday()) + (weeks * 7)
