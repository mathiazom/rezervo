from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session
from starlette import status

from rezervo.api.common import get_db, token_auth_scheme
from rezervo.auth import auth0
from rezervo.database import crud
from rezervo.settings import Settings, get_settings

router = APIRouter()


class User(BaseModel):
    name: str


@router.put("/user", response_model=User)
def upsert_user(
    user: User,
    token=Depends(token_auth_scheme),
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
):
    db_user = crud.user_from_token(db, settings, token)

    if db_user is None:
        jwt_sub = auth0.sub_from_jwt(
            token,
            settings.JWT_DOMAIN,
            settings.JWT_ALGORITHMS,
            settings.JWT_AUDIENCE,
            settings.JWT_ISSUER,
        )
        if not isinstance(jwt_sub, str):
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED)
        crud.create_user(db, user.name, jwt_sub)
    else:
        db_user.name = user.name
        db.commit()

    return user
