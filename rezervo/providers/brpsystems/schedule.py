import asyncio
from datetime import datetime, timedelta
from typing import Optional
from urllib.parse import urlencode

import requests
from pydantic import ValidationError

from rezervo.http_client import HttpClient
from rezervo.providers.brpsystems.schema import (
    BrpActivityDetails,
    BrpClass,
    BrpReceivedActivityDetails,
    BrpSubdomain,
    DetailedBrpClass,
)
from rezervo.utils.logging_utils import log

BRP_MAX_SCHEDULE_DAYS_PER_FETCH = 14


def classes_schedule_url(subdomain: BrpSubdomain, business_unit: int) -> str:
    return f"https://{subdomain}.brpsystems.com/brponline/api/ver3/businessunits/{business_unit}/groupactivities"


def class_url(subdomain: BrpSubdomain, business_unit: int, class_id: str) -> str:
    return f"https://{subdomain}.brpsystems.com/brponline/api/ver3/businessunits/{business_unit}/groupactivities/{class_id}"


def detailed_activity_url(subdomain: BrpSubdomain, activity_id: int) -> str:
    return f"https://{subdomain}.brpsystems.com/brponline/api/ver3/products/groupactivities/{activity_id}"


async def fetch_brp_class(
    subdomain: BrpSubdomain,
    business_unit: int,
    class_id: str,
) -> Optional[BrpClass]:
    async with HttpClient.singleton().get(
        class_url(subdomain, business_unit, class_id)
    ) as res:
        if res.status != requests.codes.OK:
            log.warning(
                f"Failed to fetch brp class with id {class_id}, received status {res.status}"
            )
            return None
        json_result = await res.json()
    try:
        return BrpClass(**json_result)
    except ValidationError:
        log.warning("Failed to parse brp class", json_result)
        return None


async def fetch_detailed_brp_schedule(
    subdomain: BrpSubdomain,
    schedule: list[BrpClass],
) -> list[DetailedBrpClass]:
    class_details_map: dict[int, BrpActivityDetails] = {}
    fetch_detailed_activity_tasks = []
    detected_activity_ids = set()
    for brp_class in schedule:
        activity_id = brp_class.groupActivityProduct.id
        if brp_class.groupActivityProduct.id not in detected_activity_ids:
            fetch_detailed_activity_tasks.append(
                HttpClient.singleton().get(
                    detailed_activity_url(subdomain, activity_id),
                )
            )
            detected_activity_ids.add(activity_id)
    for res in await asyncio.gather(*fetch_detailed_activity_tasks):
        if res.status != requests.codes.OK:
            log.warning(
                f"Failed to fetch class detail for {subdomain}, received status {res.status}"
            )
            continue
        details = BrpReceivedActivityDetails(**(await res.json()))
        image_url = None
        if details.assets is not None and len(details.assets) > 0:
            image_url = details.assets[min(2, len(details.assets) - 1)].contentUrl
        class_details_map[details.id] = BrpActivityDetails(
            description=details.description if details.description is not None else "",
            image_url=image_url,
        )
    return [
        DetailedBrpClass(
            **brp_class.dict(),
            activity_details=class_details_map[brp_class.groupActivityProduct.id],
        )
        for brp_class in schedule
    ]


def deduplicated_brp_schedule(classes: list[BrpClass]) -> list[BrpClass]:
    seen_class_ids = set()
    unique_classes = []
    for _class in classes:
        if _class.id in seen_class_ids:
            continue
        seen_class_ids.add(_class.id)
        unique_classes.append(_class)
    return unique_classes


async def fetch_brp_schedule(
    subdomain: BrpSubdomain,
    business_unit: int,
    days: int,
    from_date: Optional[datetime] = None,
) -> list[BrpClass]:
    classes: list[BrpClass] = []
    if from_date is None:
        now = datetime.utcnow()
        from_date = datetime(now.year, now.month, now.day)
    days_left = days
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
            HttpClient.singleton().get(
                f"{classes_schedule_url(subdomain, business_unit)}?{urlencode(query_params)}"
            )
        )
        from_date = to_date
    for res in await asyncio.gather(*fetch_schedule_tasks):
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
                log.warning("Failed to parse brp class", item)
                continue
    # remove any duplicates (if somehow classes are included in multiple batches)
    return deduplicated_brp_schedule(classes)
