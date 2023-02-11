
from datetime import datetime as dtime

from dateutil import rrule
from dateutil.rrule import rruleset
from recurrent import RecurringEvent


def ruleset_from_natural(natural):
    r = RecurringEvent()
    rule = r.parse(natural)
    print(rule)
    rules = rruleset()
    if rule is None:
        raise ValueError
    elif isinstance(rule, dtime):
        rules.rdate(rule)
    elif isinstance(rule, str):
        # WARNING: Ignores recurrences which fall un non-existing dates. Somehow. It somehow handles "every X days",
        # but "monthly" is ignored if the date of the month does not exist for that month.
        rules.rrule(rrule.rrulestr(rule))
    else:
        raise NotImplementedError
    return rules


def is_date_within_recurrence_str(dt, rule_str: str):
    base_ruleset = ruleset_from_natural("every day at 23:00 starting yesterday")
    date = dt.date()
    print(date)
    print(list(base_ruleset.xafter(dt, count=3, inc=True)))
    print(base_ruleset.after(dt, inc=True).date())
    if date != base_ruleset.after(dt, inc=True).date():
        return False
    custom_ruleset = ruleset_from_natural(rule_str)
    print(custom_ruleset.after(dt, inc=True).date())
    return date == custom_ruleset.after(dt, inc=True).date()
