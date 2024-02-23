from auth0.management import Auth0  # type: ignore
from fastapi import APIRouter, Depends, HTTPException, Response
from sqlalchemy.orm import Session
from starlette import status

from rezervo import models
from rezervo.api.common import get_db, token_auth_scheme
from rezervo.auth import auth0
from rezervo.auth.auth0 import get_auth0_management_client
from rezervo.database import crud
from rezervo.settings import Settings, get_settings

router = APIRouter()


@router.put("/user")
def upsert_user(
    response: Response,
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
    db_user = db.query(models.User).filter_by(jwt_sub=jwt_sub).one_or_none()
    if db_user is not None:
        # TODO: update user data without being rate limited by Auth0
        response.status_code = status.HTTP_204_NO_CONTENT
        return
    name = auth0.get_auth0_user_name(auth0_mgmt_client, jwt_sub)
    crud.create_user(db, name, jwt_sub)
    response.status_code = status.HTTP_201_CREATED
