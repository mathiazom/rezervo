import datetime


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


def first_date_of_week_by_offset(week_offset: int) -> datetime.datetime:
    # return the date of the first day of the week, given a week offset from the current week
    # e.g. if week_offset is 0, return the date of the first day of the current week
    #      if week_offset is 1, return the date of the first day of the next week
    first_date = datetime.date.today() + datetime.timedelta(
        days=week_offset * 7 - datetime.date.today().weekday()
    )
    # convert to datetime by attaching "earliest representable time" (aka midnight)
    return datetime.datetime.combine(first_date, datetime.datetime.min.time())
