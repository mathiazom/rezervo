import shutil
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Header, HTTPException, Response, UploadFile
from sqlalchemy.orm import Session
from starlette import status

from rezervo import models
from rezervo.api.common import get_db, token_auth_scheme
from rezervo.auth.jwt import decode_jwt_sub
from rezervo.consts import AVATAR_FILENAME_STEM, MAX_AVATAR_FILE_SIZE_BYTES
from rezervo.database import crud
from rezervo.schemas.config.user import ChainConfig, ChainIdentifier
from rezervo.schemas.schedule import BaseUserSession
from rezervo.settings import Settings, get_settings
from rezervo.utils.avatar_utils import (
    build_user_avatars_dir,
    generate_avatar_thumbnails,
    get_user_avatar_file_by_id,
    save_upload_file,
)
from rezervo.utils.logging_utils import log

router = APIRouter()


@router.put("/user", response_model=UUID)
def upsert_user(
    response: Response,
    token=Depends(token_auth_scheme),
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
):
    jwt_sub = decode_jwt_sub(
        token.credentials,
        settings.decoded_jwt_public_key(),
        settings.JWT_ALGORITHMS,
        settings.JWT_AUDIENCE,
        settings.JWT_ISSUER,
    )
    if not isinstance(jwt_sub, str):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED)
    db_user = db.query(models.User).filter_by(jwt_sub=jwt_sub).one_or_none()
    if db_user is not None:
        return db_user.id
    # TODO: create user
    # db_created_user = crud.create_user(db, name, jwt_sub)
    # response.status_code = status.HTTP_201_CREATED
    # return db_created_user.id
    raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED)


@router.get(
    "/user/sessions",
    response_model=list[BaseUserSession],
)
def get_user_sessions(
    token=Depends(token_auth_scheme),
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
):
    db_user = crud.user_from_token(db, settings, token)
    if db_user is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED)
    db_sessions = (
        db.query(models.Session)
        .filter(models.Session.user_id == db_user.id)
        .filter(
            models.Session.status.in_(
                [
                    models.SessionState.PLANNED,
                    models.SessionState.BOOKED,
                    models.SessionState.WAITLIST,
                ]
            )
        )
        .order_by(models.Session.class_data["start_time"])
        .all()
    )

    return [
        BaseUserSession(
            chain=session.chain,
            status=session.status,
            class_data=session.class_data,  # type: ignore[arg-type]
        )
        for session in db_sessions
    ]


@router.get(
    "/user/chain-configs",
    response_model=dict[ChainIdentifier, ChainConfig],
)
def get_user_chain_configs(
    token=Depends(token_auth_scheme),
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
):
    db_user = crud.user_from_token(db, settings, token)
    if db_user is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED)
    db_chain_users = db.query(models.ChainUser).filter_by(user_id=db_user.id).all()
    return {
        chain_user.chain: crud.get_chain_config(db, chain_user.chain, db_user.id)
        for chain_user in db_chain_users
    }


@router.get("/user/me/avatar/{size_name}")
def get_user_avatar(
    size_name: str,
    token=Depends(token_auth_scheme),
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
):
    db_user = crud.user_from_token(db, settings, token)
    if db_user is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED)
    file = get_user_avatar_file_by_id(db_user.id, size_name)
    if file is None:
        return Response(status_code=status.HTTP_404_NOT_FOUND)
    return Response(content=file.read_bytes(), media_type="image/webp")


@router.get("/user/{user_id}/avatar/{size_name}")
def get_user_avatar_by_id(
    user_id: UUID,
    size_name: str,
    token=Depends(token_auth_scheme),
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
):
    db_user = crud.user_from_token(db, settings, token)
    if db_user is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED)
    file = get_user_avatar_file_by_id(user_id, size_name)
    if file is None:
        return Response(status_code=status.HTTP_404_NOT_FOUND)
    return Response(content=file.read_bytes(), media_type="image/webp")


@router.put(
    "/user/me/avatar",
    status_code=status.HTTP_201_CREATED,
)
def upsert_user_avatar(
    file: UploadFile,
    token=Depends(token_auth_scheme),
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
    content_length: Annotated[int | None, Header()] = None,
):
    db_user = crud.user_from_token(db, settings, token)
    if db_user is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED)
    if content_length is None or file is None or file.filename is None:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST)
    if content_length > MAX_AVATAR_FILE_SIZE_BYTES:
        raise HTTPException(status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE)
    with TemporaryDirectory() as temp_avatar_dir_str:
        temp_avatar_dir = Path(temp_avatar_dir_str)
        avatar_path = (
            temp_avatar_dir / f"{AVATAR_FILENAME_STEM}{Path(file.filename).suffix}"
        )
        save_upload_file(file, avatar_path, MAX_AVATAR_FILE_SIZE_BYTES)
        generate_avatar_thumbnails(avatar_path)
        avatar_path.unlink()
        user_avatar_dir = build_user_avatars_dir(db_user.id)
        if user_avatar_dir is None:
            raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR)
        if user_avatar_dir.exists():
            shutil.rmtree(user_avatar_dir)
        shutil.move(temp_avatar_dir, user_avatar_dir)
        log.info(f"Successfully updated avatar for {db_user.name}")


@router.delete("/user/me/avatar", status_code=status.HTTP_204_NO_CONTENT)
def delete_user_avatar(
    token=Depends(token_auth_scheme),
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
):
    db_user = crud.user_from_token(db, settings, token)
    if db_user is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED)
    user_avatar_dir = build_user_avatars_dir(db_user.id)
    if user_avatar_dir is None or not user_avatar_dir.exists():
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND)
    shutil.rmtree(user_avatar_dir)
