import asyncio
import datetime
from typing import Callable, Optional

from rezervo.http_client import HttpClient
from rezervo.providers.sats.consts import SATS_EXPOSED_CLASSES_DAYS_INTO_FUTURE
from rezervo.providers.sats.schema import (
    SatsClass,
    SatsScheduleResponse,
)
from rezervo.providers.sats.urls import SCHEDULE_URL

BATCH_SIZE = 20  # Limited by the Sats API pagination
TASK_COUNT = 5  # Number of parallel fetchers


def is_schedule_fetchable_for_date(date: datetime.date) -> bool:
    now_date = datetime.datetime.now().date()
    return (
        now_date
        <= date
        < (now_date + datetime.timedelta(days=SATS_EXPOSED_CLASSES_DAYS_INTO_FUTURE))
    )


async def fetch_sats_classes_with_offset(
    club_ids: list[str], date: datetime.datetime, offset: int
) -> Optional[list[SatsClass]]:
    async with HttpClient.singleton().post(
        SCHEDULE_URL,
        json={
            "clubIds": ",".join(club_ids),
            "date": date.strftime("%Y-%m-%d"),
            "offset": offset,
        },
    ) as res:
        if not res.ok:
            return None
        return SatsScheduleResponse(**(await res.json())).classes


async def fetch_classes_batch_task(
    club_ids: list[str],
    date: datetime.datetime,
    find_class_comparator_fn: Callable[[SatsClass], bool] | None,
    start_batch: int,
    batch_step: int,
    batch_size: int,
) -> list[SatsClass]:
    batch_classes: list[SatsClass] = []
    offset = batch_size * start_batch
    while True:
        classes = await fetch_sats_classes_with_offset(club_ids, date, offset)
        if classes is None or len(classes) == 0:
            break
        if find_class_comparator_fn is not None:
            for sats_class in classes:
                if find_class_comparator_fn(sats_class):
                    return [sats_class]
        else:
            batch_classes.extend(classes)
        offset += batch_size * batch_step
    return batch_classes


async def find_sats_class(
    club_ids: list[str],
    date: datetime.datetime,
    comparator_fn: Callable[[SatsClass], bool],
) -> Optional[SatsClass]:
    tasks = [
        asyncio.create_task(
            fetch_classes_batch_task(
                club_ids,
                date,
                comparator_fn,
                i,
                TASK_COUNT,
                BATCH_SIZE,
            )
        )
        for i in range(TASK_COUNT)
    ]
    for coro in asyncio.as_completed(tasks):
        try:
            res = await coro
        except asyncio.CancelledError:
            for t in tasks:
                t.cancel()
            raise
        if res is not None and len(res) > 0:
            for t in tasks:
                t.cancel()
            return res[0]
    return None


async def fetch_sats_classes(
    club_ids: list[str],
    date: datetime.datetime,
) -> list[SatsClass]:
    classes = []
    for res in await asyncio.gather(
        *[
            fetch_classes_batch_task(
                club_ids,
                date,
                None,
                i,
                TASK_COUNT,
                BATCH_SIZE,
            )
            for i in range(TASK_COUNT)
        ]
    ):
        classes.extend(res)
    return classes
