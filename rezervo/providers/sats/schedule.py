import asyncio
from datetime import datetime

from rezervo.http_client import HttpClient
from rezervo.providers.sats.schema import SatsClass, SatsScheduleResponse
from rezervo.providers.sats.urls import SCHEDULE_URL

BATCH_SIZE = 20  # Limited by the Sats API pagination
TASK_COUNT = 5  # Number of parallel fetchers


async def fetch_sats_classes_with_offset(
    club_ids: list[str], date: datetime, offset: int
) -> list[SatsClass]:
    response = await HttpClient.singleton().post(
        SCHEDULE_URL,
        json={
            "clubIds": ",".join(club_ids),
            "date": date.strftime("%Y-%m-%d"),
            "offset": offset,
        },
    )
    return SatsScheduleResponse(**await response.json()).classes


async def fetch_classes_batch_task(
    club_ids: list[str],
    date: datetime,
    start_batch: int,
    batch_step: int,
    batch_size: int,
) -> list[SatsClass]:
    all_classes: list[SatsClass] = []
    offset = batch_size * start_batch
    while True:
        classes = await fetch_sats_classes_with_offset(club_ids, date, offset)
        if not classes:
            break
        all_classes.extend(classes)
        offset += batch_size * batch_step
    return all_classes


async def fetch_sats_classes(club_ids: list[str], date: datetime) -> list[SatsClass]:
    all_classes = []
    for classes in await asyncio.gather(
        *(
            fetch_classes_batch_task(club_ids, date, i, TASK_COUNT, BATCH_SIZE)
            for i in range(TASK_COUNT)
        )
    ):
        all_classes.extend(classes)
    return all_classes
