import asyncio
from typing import Optional
from uuid import UUID

from rezervo import models
from rezervo.chains.active import ACTIVE_CHAIN_IDENTIFIERS, get_chain
from rezervo.database import crud
from rezervo.database.database import SessionLocal
from rezervo.models import SessionState
from rezervo.schemas.config.user import ChainIdentifier
from rezervo.schemas.schedule import (
    RezervoClass,
    UserSession,
    session_model_from_user_session,
)
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
    for cu, user_sessions in zip(
        chain_users,
        await asyncio.gather(
            *[
                get_chain(chain_identifier).fetch_sessions(chain_user)
                for chain_user in chain_users
            ]
        ),
    ):
        with SessionLocal() as db:
            crud.upsert_user_chain_sessions(
                db, cu.user_id, chain_identifier, user_sessions
            )


async def pull_sessions(
    chain_identifier: Optional[ChainIdentifier] = None, user_id: Optional[UUID] = None
):
    if chain_identifier is not None:
        await pull_chain_sessions(chain_identifier, user_id)
        return
    await asyncio.gather(
        *[pull_chain_sessions(i, user_id) for i in ACTIVE_CHAIN_IDENTIFIERS]
    )


async def upsert_booked_session(
    chain_identifier: ChainIdentifier, user_id: UUID, _class: RezervoClass
):
    session = session_model_from_user_session(
        UserSession(
            chain=chain_identifier,
            class_id=_class.id,
            user_id=user_id,
            status=(
                SessionState.BOOKED
                if _class.available_slots > 0
                else SessionState.WAITLIST
            ),
            class_data=_class,
        )
    )
    with SessionLocal() as db:
        existing_session = (
            db.query(models.Session)
            .filter_by(chain=chain_identifier, user_id=user_id, class_id=_class.id)
            .one_or_none()
        )
        if existing_session is not None:
            existing_session.status = session.status
            existing_session.class_data = session.class_data
        else:
            db.add(session)
        db.commit()


async def remove_session(
    chain_identifier: ChainIdentifier, user_id: UUID, class_id: str
):
    with SessionLocal() as db:
        db.query(models.Session).filter_by(
            chain=chain_identifier, user_id=user_id, class_id=class_id
        ).delete()
        db.commit()
