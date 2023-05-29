from typing import Optional
from uuid import UUID

from sqlalchemy import delete
from sqlalchemy.orm import Session

from sit_rezervo import models
from sit_rezervo.auth import auth0
from sit_rezervo.models import SessionState
from sit_rezervo.schemas.config import user, admin
from sit_rezervo.schemas.config.user import UserConfig as UserConfig
from sit_rezervo.schemas.session import UserSession


def user_from_token(db: Session, settings, token) -> Optional[models.User]:
    jwt_sub = auth0.sub_from_jwt(
        token,
        settings.JWT_DOMAIN,
        settings.JWT_ALGORITHMS,
        settings.JWT_AUDIENCE,
        settings.JWT_ISSUER
    )
    if jwt_sub is None:
        return None
    return db.query(models.User).filter_by(jwt_sub=jwt_sub).one_or_none()


def get_config_by_id(db: Session, config_id: UUID) -> Optional[models.Config]:
    db_config_query = db.query(models.Config).filter_by(id=config_id)
    db_config = db_config_query.one_or_none()
    return db_config


def create_user(db: Session, name: str, jwt_sub: str):
    db_user = models.User(name=name, jwt_sub=jwt_sub)
    db.add(db_user)
    db.commit()
    db.refresh(db_user)
    return db_user


def delete_user(db: Session, user_id: UUID):
    db_user = db.get(models.User, user_id)
    db.delete(db_user)
    db.commit()


def create_config(db: Session, user_id: UUID, sit_email: str, sit_password: str,
                  slack_id: Optional[str]) -> models.Config:
    db_config = models.Config(
        user_id=user_id,
        admin_config=admin.AdminConfig(
            auth=admin.Auth(
                email=sit_email,
                password=sit_password
            ),
            notifications=admin.Notifications(
                slack=admin.Slack(
                    user_id=slack_id
                )
            ) if slack_id is not None else None
        ).dict(),
        config=user.UserConfig().dict()
    )
    db.add(db_config)
    db.commit()
    db.refresh(db_config)
    return db_config


def get_user_config(db: Session, user_id: UUID) -> Optional[models.Config]:
    db_config_query = db.query(models.Config).filter_by(user_id=user_id)
    db_config: Optional[models.Config] = db_config_query.one_or_none()
    return db_config


def update_user_config(db: Session, user_id: UUID, config: UserConfig) -> Optional[models.Config]:
    db_config = get_user_config(db, user_id)
    db_config.config = config.dict()
    db.commit()
    db.refresh(db_config)
    return db_config


def upsert_user_sessions(db: Session, user_id: UUID, user_sessions: list[UserSession]):
    delete_unconfirmed_stmt = delete(models.Session).where(
        models.Session.user_id == user_id,
        models.Session.status != SessionState.CONFIRMED
    )
    db.execute(delete_unconfirmed_stmt)
    for s in user_sessions:
        db.merge(models.Session(**s.dict()))
    db.commit()
