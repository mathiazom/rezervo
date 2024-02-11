import asyncio
from typing import Optional
from uuid import UUID

from crontab import CronTab
from rich import print as rprint

from rezervo import models
from rezervo.chains.active import ACTIVE_CHAIN_IDENTIFIERS, get_chain
from rezervo.database import crud
from rezervo.database.database import SessionLocal
from rezervo.schemas.config.config import Config
from rezervo.schemas.config.user import ChainConfig, ChainIdentifier
from rezervo.utils.cron_utils import (
    build_cron_jobs_from_config_task,
    upsert_jobs_by_comment,
)
from rezervo.utils.logging_utils import err


async def refresh_cron(
    user_id: Optional[UUID] = None,
    chain_identifiers: list[ChainIdentifier] = ACTIVE_CHAIN_IDENTIFIERS,
):
    chains = [get_chain(c) for c in chain_identifiers]
    recurring_booking_user_configs: list[tuple[Config, ChainConfig, models.User]] = []
    with SessionLocal() as db:
        users_query = db.query(models.User)
        if user_id is not None:
            users_query = users_query.filter_by(id=user_id)
        users = users_query.all()
        for user in users:
            config = crud.get_user_config_by_id(db, user.id)
            if config is None:
                err.log(f"User '{user.name}' has no config, skipping...")
                continue
            for chain in chains:
                chain_config = crud.get_chain_config(db, chain.identifier, user.id)
                if chain_config is None:
                    continue
                recurring_booking_user_configs.append((config, chain_config, user))
    # write all changes in a single crontab session to avoid race conditions
    with CronTab(user=True) as crontab:
        for chain, username, comment_pattern, jobs in await asyncio.gather(
            *[
                build_cron_jobs_from_config_task(crontab, config, chain_config, user)
                for config, chain_config, user in recurring_booking_user_configs
            ]
        ):
            upsert_jobs_by_comment(crontab, comment_pattern, jobs)
            rprint(f":heavy_check_mark: '{chain}' crontab updated for '{username}'")
