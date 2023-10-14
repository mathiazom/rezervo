from datetime import datetime, timedelta
from typing import List, Union
from urllib.parse import urlencode

import requests

from rezervo.providers.brpsystems.schema import (
    BrpClass,
    BrpSubdomain,
)

BRP_MAX_SCHEDULE_DAYS_PER_FETCH = 14


def classes_schedule_url(subdomain: BrpSubdomain, business_unit: int) -> str:
    return f"https://{subdomain.value}.brpsystems.com/brponline/api/ver3/businessunits/{business_unit}/groupactivities"


def fetch_brp_schedule(
    subdomain: BrpSubdomain, business_unit: int, days: int, from_date: datetime = None
) -> Union[List[BrpClass], None]:
    classes: list[BrpClass] = []
    if from_date is None:
        now = datetime.utcnow()
        from_date = datetime(now.year, now.month, now.day)
    days_left = days
    while days_left > 0:
        batch_size = min(BRP_MAX_SCHEDULE_DAYS_PER_FETCH, days_left)
        days_left -= batch_size
        to_date = from_date + timedelta(days=batch_size)
        query_params = {
            "period.start": from_date.strftime("%Y-%m-%dT%H:%M:%S") + ".000Z",
            "period.end": to_date.strftime("%Y-%m-%dT%H:%M:%S") + ".000Z",
        }
        res = requests.get(
            f"{classes_schedule_url(subdomain, business_unit)}?{urlencode(query_params)}"
        )
        if res.status_code != requests.codes.OK:
            raise Exception("Failed to fetch brp schedule")
        classes.extend(
            [
                BrpClass(**item)
                for item in res.json()
                if item.get("bookableEarliest") is not None
                and item.get("bookableLatest") is not None
            ]
        )
        from_date = to_date
    # TODO: handle unlikely duplicates (if somehow classes are included in multiple batches)
    return classes
