import asyncio
from typing import Optional
from uuid import UUID

from rezervo import models
from rezervo.chains.active import ACTIVE_CHAIN_IDENTIFIERS, get_chain
from rezervo.database import crud
from rezervo.database.database import SessionLocal
from rezervo.models import SessionState
from rezervo.schemas.config.user import ChainConfig, ChainIdentifier
from rezervo.schemas.schedule import (
    BookingResult,
    RezervoClass,
    SessionRezervoClass,
    UserSession,
    session_model_from_user_session,
)
from rezervo.utils.config_utils import (
    class_config_recurrent_id,
    rezervo_class_recurrent_id,
)
from rezervo.utils.logging_utils import log


async def pull_chain_sessions(
    chain_identifier: ChainIdentifier, user_id: Optional[UUID] = None
):
    if user_id is not None:
        with SessionLocal() as db:
            chain_user = crud.get_chain_user(db, chain_identifier, user_id)
        if chain_user is None:
            log.error(
                f"Chain user '{user_id}' not found for chain '{chain_identifier}'"
            )
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


def upsert_session(
    chain_identifier: ChainIdentifier,
    user_id: UUID,
    _class: RezervoClass,
    status: SessionState,
    position_in_wait_list: Optional[int] = None,
):
    session = session_model_from_user_session(
        UserSession(
            chain=chain_identifier,
            class_id=_class.id,
            user_id=user_id,
            status=status,
            position_in_wait_list=position_in_wait_list,
            class_data=SessionRezervoClass(**_class.dict()),
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


def upsert_booked_session(
    chain_identifier: ChainIdentifier,
    user_id: UUID,
    _class: RezervoClass,
    booking_result: BookingResult,
):
    upsert_session(
        chain_identifier,
        user_id,
        _class,
        (
            (
                SessionState.BOOKED
                if (_class.available_slots or (1 - (_class.waiting_list_count or 0)))
                > 0
                else SessionState.WAITLIST
            )
            if booking_result.status is SessionState.UNKNOWN
            else booking_result.status
        ),
        booking_result.position_in_wait_list,
    )


async def remove_session(
    chain_identifier: ChainIdentifier, user_id: UUID, class_id: str
):
    with SessionLocal() as db:
        db.query(models.Session).filter_by(
            chain=chain_identifier, user_id=user_id, class_id=class_id
        ).delete()
        db.commit()


async def remove_sessions(
    chain_identifier: ChainIdentifier,
    user_id: UUID,
    recurrent_ids_to_remove: list[str],
    session_state: SessionState,
):
    with SessionLocal() as db:
        user_planned_sessions = (
            db.query(models.Session)
            .filter(
                models.Session.chain == chain_identifier,
                models.Session.user_id == user_id,
                models.Session.status == session_state,
            )
            .all()
        )
        for session in user_planned_sessions:
            if (
                rezervo_class_recurrent_id(UserSession.from_orm(session).class_data)
                in recurrent_ids_to_remove
            ):
                db.delete(session)
        db.commit()


async def update_planned_sessions(
    chain_identifier: ChainIdentifier,
    user_id: UUID,
    previous_config: ChainConfig | None,
    updated_config: ChainConfig,
):
    previous_class_ids = (
        set()
        if previous_config is None or not previous_config.active
        else {
            class_config_recurrent_id(_class)
            for _class in previous_config.recurring_bookings
        }
    )
    updated_class_ids = (
        set()
        if not updated_config.active
        else {
            class_config_recurrent_id(_class)
            for _class in updated_config.recurring_bookings
        }
    )

    removed_class_ids = previous_class_ids - updated_class_ids
    added_class_ids = updated_class_ids - previous_class_ids

    if len(removed_class_ids) > 0:
        await remove_sessions(
            chain_identifier, user_id, list(removed_class_ids), SessionState.PLANNED
        )

    find_session_class_tasks = []
    for _class_config in updated_config.recurring_bookings:
        if class_config_recurrent_id(_class_config) in added_class_ids:
            find_session_class_tasks.append(
                get_chain(chain_identifier).find_class(_class_config)
            )
    for session_class_data in await asyncio.gather(*find_session_class_tasks):
        if not isinstance(session_class_data, RezervoClass):
            log.error(
                f"Failed to generate planned session. Class not found: {session_class_data}"
            )
            continue
        upsert_session(
            chain_identifier, user_id, session_class_data, SessionState.PLANNED
        )
