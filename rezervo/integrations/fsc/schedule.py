from datetime import datetime, timedelta
from typing import List, Union
from urllib.parse import urlencode

import requests

from rezervo.integrations.fsc.consts import CLASSES_SCHEDULE_URL
from rezervo.integrations.fsc.schema import (
    FscClass,
    FscWeekScheduleResponse,
)


def fetch_fsc_schedule() -> Union[List[FscClass], None]:
    now = datetime.utcnow()
    from_date = datetime(now.year, now.month, now.day)
    query_params = {
        "period_start": from_date.strftime("%Y-%m-%dT%H:%M:%S") + ".000Z",
        "period_end": (from_date + timedelta(weeks=1)).strftime("%Y-%m-%dT%H:%M:%S")
        + ".000Z",
    }
    res = requests.get(f"{CLASSES_SCHEDULE_URL}?{urlencode(query_params)}")
    if res.status_code != requests.codes.OK:
        return None
    return FscWeekScheduleResponse(**res.json()).data
