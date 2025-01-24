import datetime

from isoweek import Week  # type: ignore[import-untyped]


def readable_seconds(s: float):
    minutes = int(s / 60)
    seconds = int(s % 60)
    return "".join(
        [
            (
                f"{minutes} minute{'s' if minutes > 1 else ''}{' and ' if seconds > 0 else ''}"
                if minutes > 0
                else ""
            ),
            f"{seconds} second{'s' if seconds > 1 else ''}" if seconds > 0 else "",
        ]
    )


def total_days_for_next_whole_weeks(weeks: int):
    # number of days left of the current week plus days in `weeks` number of whole weeks
    return (7 - datetime.datetime.now().weekday()) + (weeks * 7)


def from_compact_iso_week(compact_iso_week: str) -> datetime.datetime:
    week_year = int(compact_iso_week[0:4])
    week_number = int(compact_iso_week[5:7])

    first_date = Week(week_year, week_number).monday()
    # convert to datetime by attaching "earliest representable time" (aka midnight)
    return datetime.datetime.combine(first_date, datetime.datetime.min.time())


def compact_iso_week_str(date: datetime.datetime):
    return date.strftime("%GW%V")
