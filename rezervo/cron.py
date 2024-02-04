import asyncio
from typing import Optional
from uuid import UUID

from rich import print as rprint

from rezervo import models
from rezervo.chains.active import ACTIVE_CHAIN_IDENTIFIERS, get_chain
from rezervo.database import crud
from rezervo.database.database import SessionLocal
from rezervo.schemas.config.config import Config
from rezervo.schemas.config.user import ChainConfig, ChainIdentifier
from rezervo.utils.cron_utils import upsert_booking_crontab
from rezervo.utils.logging_utils import err


async def upsert_booking_crontab_task(
    config: Config, chain_config: ChainConfig, user: models.User
):
    await upsert_booking_crontab(config, chain_config, user)
    return chain_config.chain, user.name


async def refresh_cron(
    user_id: Optional[UUID] = None,
    chain_identifiers: list[ChainIdentifier] = ACTIVE_CHAIN_IDENTIFIERS,
):
    chains = [get_chain(c) for c in chain_identifiers]
    upsert_tasks = []
    with SessionLocal() as db:
        users_query = db.query(models.User)
        if user_id is not None:
            users_query = users_query.filter_by(id=user_id)
        users = users_query.all()
        for u in users:
            config = crud.get_user_config_by_id(db, u.id)
            if config is None:
                err.log(f"User '{u.name}' has no config, skipping...")
                continue
            for c in chains:
                ic = crud.get_chain_config(db, c.identifier, u.id)
                if ic is not None:
                    upsert_tasks.append(upsert_booking_crontab_task(config, ic, u))
    for chain, username in await asyncio.gather(*upsert_tasks):
        rprint(f":heavy_check_mark: '{chain}' crontab updated for '{username}'")
