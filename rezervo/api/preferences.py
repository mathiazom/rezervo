from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from starlette import status

from rezervo.api.common import get_db, token_auth_scheme
from rezervo.database import crud
from rezervo.schemas.config.user import UserPreferences
from rezervo.settings import Settings, get_settings

router = APIRouter()


@router.get("/preferences", response_model=UserPreferences)
def get_user_preferences(
    token=Depends(token_auth_scheme),
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
):
    db_user = crud.user_from_token(db, settings, token)
    if db_user is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED)
    return UserPreferences(**db_user.preferences)  # type: ignore


@router.put("/preferences", response_model=UserPreferences)
def upsert_user_preferences(
    preferences: UserPreferences,
    token=Depends(token_auth_scheme),
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
):
    db_user = crud.user_from_token(db, settings, token)
    if db_user is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED)
    db_user.preferences = preferences.dict()
    db.commit()
    db.refresh(db_user)
    return db_user.preferences
