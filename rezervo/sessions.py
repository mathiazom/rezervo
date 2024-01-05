from typing import Optional
from uuid import UUID

from rich import print as rprint

from rezervo.chains.active import ACTIVE_CHAIN_IDENTIFIERS, get_chain
from rezervo.database import crud
from rezervo.database.database import SessionLocal
from rezervo.schemas.config.user import ChainIdentifier
from rezervo.schemas.schedule import UserSession
from rezervo.utils.logging_utils import err


async def pull_chain_sessions(
    chain_identifier: ChainIdentifier, user_id: Optional[UUID] = None
):
    if user_id is not None:
        with SessionLocal() as db:
            chain_user = crud.get_chain_user(db, chain_identifier, user_id)
        if chain_user is None:
            err.log(f"Chain user {user_id} not found for chain {chain_identifier}")
            return
        chain_users = [chain_user]
    else:
        with SessionLocal() as db:
            chain_users = crud.get_chain_users(db, chain_identifier)
    sessions: dict[UUID, list[UserSession]] = {}
    for chain_user in chain_users:
        rprint(
            f":right_arrow_curving_down: Pulling user sessions from '{chain_identifier}' for '{chain_user.username}' ..."
        )
        sessions[chain_user.user_id] = await get_chain(chain_identifier).fetch_sessions(
            chain_user
        )
    with SessionLocal() as db:
        for uid, user_sessions in sessions.items():
            crud.upsert_user_chain_sessions(db, uid, chain_identifier, user_sessions)


async def pull_sessions(
    chain_identifier: Optional[ChainIdentifier] = None, user_id: Optional[UUID] = None
):
    if chain_identifier is not None:
        await pull_chain_sessions(chain_identifier, user_id)
        return
    for i in ACTIVE_CHAIN_IDENTIFIERS:
        await pull_chain_sessions(i, user_id)
