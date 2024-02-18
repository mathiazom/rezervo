from auth0.management import Auth0
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from starlette import status

from rezervo.api.common import get_db, token_auth_scheme
from rezervo.auth import auth0
from rezervo.auth.auth0 import get_auth0_management_client
from rezervo.database import crud
from rezervo.settings import Settings, get_settings

router = APIRouter()


@router.put("/user", status_code=status.HTTP_204_NO_CONTENT)
def upsert_user(
    token=Depends(token_auth_scheme),
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
    auth0_mgmt_client: Auth0 = Depends(get_auth0_management_client),
):
    jwt_sub = auth0.sub_from_jwt(
        token,
        settings.JWT_DOMAIN,
        settings.JWT_ALGORITHMS,
        settings.JWT_AUDIENCE,
        settings.JWT_ISSUER,
    )
    if not isinstance(jwt_sub, str):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED)

    name = auth0_mgmt_client.users.get(jwt_sub)["name"]  # type: ignore

    db_user = crud.user_from_token(db, settings, token)
    if db_user is None:
        crud.create_user(db, name, jwt_sub)
    else:
        db_user.name = name
        db.commit()
