from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from starlette import status

from rezervo.api.common import get_db, token_auth_scheme
from rezervo.chains.common import check_in_user
from rezervo.database import crud
from rezervo.schemas.camel import CamelModel
from rezervo.schemas.config.app import AppConfig
from rezervo.schemas.config.config import read_app_config
from rezervo.schemas.config.user import ChainIdentifier
from rezervo.utils.logging_utils import log

router = APIRouter()


class CheckInPayload(CamelModel):
    terminal_id: str
    print_ticket: bool


@router.post("/{chain_identifier}/check-in")
async def check_in(
    chain_identifier: ChainIdentifier,
    payload: CheckInPayload,
    token=Depends(token_auth_scheme),
    db: Session = Depends(get_db),
    app_config: AppConfig = Depends(read_app_config),
):
    db_user = crud.user_from_token(db, app_config, token)
    if db_user is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED)

    chain_user = crud.get_chain_user(db, chain_identifier, db_user.id)
    if chain_user is None:
        log.warning(f"No '{chain_identifier}' user for given user id")
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED)

    success = await check_in_user(
        chain_identifier, chain_user, payload.terminal_id, payload.print_ticket
    )

    if not success:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR)
