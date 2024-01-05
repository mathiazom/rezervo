import asyncio
from datetime import datetime, timedelta
from typing import List, Optional
from urllib.parse import urlencode

import aiohttp
import requests
from pydantic import ValidationError

from rezervo.providers.brpsystems.schema import (
    BrpActivityDetails,
    BrpClass,
    BrpReceivedActivityDetails,
    BrpSubdomain,
    DetailedBrpClass,
)
from rezervo.utils.logging_utils import warn

BRP_MAX_SCHEDULE_DAYS_PER_FETCH = 14


def classes_schedule_url(subdomain: BrpSubdomain, business_unit: int) -> str:
    return f"https://{subdomain}.brpsystems.com/brponline/api/ver3/businessunits/{business_unit}/groupactivities"


def class_url(subdomain: BrpSubdomain, business_unit: int, class_id: str) -> str:
    return f"https://{subdomain}.brpsystems.com/brponline/api/ver3/businessunits/{business_unit}/groupactivities/{class_id}"


def detailed_activity_url(subdomain: BrpSubdomain, activity_id: int) -> str:
    return f"https://{subdomain}.brpsystems.com/brponline/api/ver3/products/groupactivities/{activity_id}"


def fetch_brp_class(
    subdomain: BrpSubdomain,
    business_unit: int,
    class_id: str,
) -> Optional[BrpClass]:
    res = requests.get(class_url(subdomain, business_unit, class_id))
    if res.status_code != requests.codes.OK:
        warn.log(
            f"Failed to fetch brp class with id {class_id}, received status {res.status_code}"
        )
        return None
    try:
        return BrpClass(**res.json())
    except ValidationError:
        warn.log("Failed to parse brp class", res.json())
        return None


async def fetch_detailed_brp_schedule(
    subdomain: BrpSubdomain,
    schedule: List[BrpClass],
) -> List[DetailedBrpClass]:
    class_details_map: dict[int, BrpActivityDetails] = {}
    async with aiohttp.ClientSession() as session:
        fetch_detailed_activity_tasks = []
        detected_activity_ids = set()
        for brp_class in schedule:
            activity_id = brp_class.groupActivityProduct.id
            if brp_class.groupActivityProduct.id not in detected_activity_ids:
                fetch_detailed_activity_tasks.append(
                    session.get(detailed_activity_url(subdomain, activity_id))
                )
                detected_activity_ids.add(activity_id)
        for async_res in asyncio.as_completed(fetch_detailed_activity_tasks):
            res = await async_res
            if res.status != requests.codes.OK:
                warn.log(
                    f"Failed to fetch class detail for {subdomain} class with id {activity_id}, "
                    f"received status {res.status}"
                )
                continue
            details = BrpReceivedActivityDetails(**(await res.json()))
            image_url = None
            if details.assets is not None and len(details.assets) > 0:
                image_url = details.assets[min(2, len(details.assets) - 1)].contentUrl
            class_details_map[activity_id] = BrpActivityDetails(
                description=details.description
                if details.description is not None
                else "",
                image_url=image_url,
            )
    return [
        DetailedBrpClass(
            **brp_class.dict(), activity_details=class_details_map[activity_id]
        )
        for brp_class in schedule
    ]


async def fetch_brp_schedule(
    subdomain: BrpSubdomain,
    business_unit: int,
    days: int,
    from_date: Optional[datetime] = None,
) -> List[BrpClass]:
    classes: list[BrpClass] = []
    if from_date is None:
        now = datetime.utcnow()
        from_date = datetime(now.year, now.month, now.day)
    days_left = days
    async with aiohttp.ClientSession() as session:
        fetch_schedule_tasks = []
        while days_left > 0:
            batch_size = min(BRP_MAX_SCHEDULE_DAYS_PER_FETCH, days_left)
            days_left -= batch_size
            to_date = from_date + timedelta(days=batch_size)
            query_params = {
                "period.start": from_date.strftime("%Y-%m-%dT%H:%M:%S") + ".000Z",
                "period.end": to_date.strftime("%Y-%m-%dT%H:%M:%S") + ".000Z",
            }
            fetch_schedule_tasks.append(
                session.get(
                    f"{classes_schedule_url(subdomain, business_unit)}?{urlencode(query_params)}"
                )
            )
        for async_res in asyncio.as_completed(fetch_schedule_tasks):
            res = await async_res
            if res.status != requests.codes.OK:
                raise Exception("Failed to fetch brp schedule")
            for item in await res.json():
                if (
                    item.get("bookableEarliest") is None
                    or item.get("bookableLatest") is None
                ):
                    continue
                try:
                    classes.append(BrpClass(**item))
                except ValidationError:
                    warn.log("Failed to parse brp class", item)
                    continue
            from_date = to_date
    # TODO: handle unlikely duplicates (if somehow classes are included in multiple batches)
    return classes
