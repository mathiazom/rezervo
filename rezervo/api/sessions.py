from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from starlette import status

from rezervo import models
from rezervo.api.common import get_db, token_auth_scheme
from rezervo.database import crud
from rezervo.schemas.community import UserRelationship
from rezervo.schemas.config.user import ChainIdentifier
from rezervo.schemas.schedule import UserNameSessionStatus, UserSession
from rezervo.settings import Settings, get_settings

router = APIRouter()


@router.get(
    "/{chain_identifier}/sessions",
    response_model=dict[str, list[UserNameSessionStatus]],
)
def get_sessions_index(
    chain_identifier: ChainIdentifier,
    token=Depends(token_auth_scheme),
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
):
    db_user = crud.user_from_token(db, settings, token)
    if db_user is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED)
    db_sessions = (
        db.query(models.Session)
        .filter(
            models.Session.status != models.SessionState.PLANNED,
            models.Session.chain == chain_identifier,
        )
        .all()
    )
    user_relationship_index = crud.get_user_relationship_index(db, db_user.id)
    friendly_db_sessions = [
        dbs
        for dbs in db_sessions
        if dbs.user_id == db_user.id
        or user_relationship_index.get(dbs.user_id) == UserRelationship.FRIEND
    ]
    user_name_lookup = {u.id: u.name for u in db.query(models.User).all()}
    session_dict: dict[str, list[UserNameSessionStatus]] = {}
    for db_session in friendly_db_sessions:
        session = UserSession.from_orm(db_session)
        class_id = session.class_id
        if class_id not in session_dict:
            session_dict[class_id] = []
        session_dict[class_id].append(
            UserNameSessionStatus(
                is_self=session.user_id == db_user.id,
                user_name=user_name_lookup[session.user_id],
                status=session.status,
            )
        )
    return session_dict
