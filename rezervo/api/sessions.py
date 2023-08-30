from auth0.management import Auth0
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from starlette import status

from rezervo import models
from rezervo.api.common import get_db, token_auth_scheme
from rezervo.auth.auth0 import get_auth0_management_client
from rezervo.database import crud
from rezervo.schemas.config.user import IntegrationIdentifier
from rezervo.schemas.schedule import UserNameSessionStatus, UserSession
from rezervo.settings import Settings, get_settings

router = APIRouter()


@router.get(
    "/{integration}/sessions", response_model=dict[str, list[UserNameSessionStatus]]
)
def get_sessions_index(
    integration: IntegrationIdentifier,
    token=Depends(token_auth_scheme),
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
    auth0_mgmt_client: Auth0 = Depends(get_auth0_management_client),
):
    db_user = crud.user_from_token(db, settings, token)
    if db_user is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED)
    db_sessions = (
        db.query(models.Session)
        .filter(
            models.Session.status != models.SessionState.PLANNED,
            models.Session.integration == integration,
        )
        .all()
    )
    user_name_lookup = {
        u.id: auth0_mgmt_client.users.get(u.jwt_sub)["name"]
        for u in db.query(models.User).all()
    }
    session_dict: dict[str, list[UserNameSessionStatus]] = {}
    for db_session in db_sessions:
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
