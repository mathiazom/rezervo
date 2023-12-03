from typing import Optional
from uuid import UUID

from sqlalchemy import delete
from sqlalchemy.orm import Session

from rezervo import models
from rezervo.auth import auth0
from rezervo.models import SessionState
from rezervo.schemas.config import admin
from rezervo.schemas.config.admin import AdminConfig
from rezervo.schemas.config.config import (
    Config,
    PushNotificationSubscription,
    PushNotificationSubscriptionKeys,
    config_from_stored,
)
from rezervo.schemas.config.user import (
    IntegrationConfig,
    IntegrationIdentifier,
    IntegrationUser,
    IntegrationUserCredentials,
    IntegrationUserProfile,
    UserPreferences,
    get_integration_config_from_integration_user,
)
from rezervo.schemas.schedule import UserSession, session_model_from_user_session
from rezervo.utils.ical_utils import generate_calendar_token


def user_from_token(db: Session, settings, token) -> Optional[models.User]:
    jwt_sub = auth0.sub_from_jwt(
        token,
        settings.JWT_DOMAIN,
        settings.JWT_ALGORITHMS,
        settings.JWT_AUDIENCE,
        settings.JWT_ISSUER,
    )
    if jwt_sub is None:
        return None
    return db.query(models.User).filter_by(jwt_sub=jwt_sub).one_or_none()


def create_user(db: Session, name: str, jwt_sub: str, slack_id: Optional[str] = None):
    db_user = models.User(
        name=name,
        jwt_sub=jwt_sub,
        cal_token=generate_calendar_token(),
        admin_config=admin.AdminConfig(
            notifications=admin.Notifications(slack=admin.Slack(user_id=slack_id))
            if slack_id is not None
            else None,
        ).dict(),
        preferences=UserPreferences().dict(),
    )
    db.add(db_user)
    db.commit()
    db.refresh(db_user)
    return db_user


def upsert_integration_user(
    db: Session,
    user_id: UUID,
    integration: IntegrationIdentifier,
    creds: IntegrationUserCredentials,
):
    db_integration_user = (
        db.query(models.IntegrationUser)
        .filter_by(user_id=user_id, integration=integration)
        .one_or_none()
    )
    if db_integration_user is None:
        db_integration_user = models.IntegrationUser(
            user_id=user_id,
            integration=integration,
            username=creds.username,
            password=creds.password,
        )
        db.add(db_integration_user)
    else:
        if (
            db_integration_user.username == creds.username
            and db_integration_user.password == creds.password
        ):
            return db_integration_user
        db_integration_user.auth_token = None  # forget token for previous credentials
        db_integration_user.username = creds.username
        db_integration_user.password = creds.password
    db.commit()
    db.refresh(db_integration_user)
    return db_integration_user


def upsert_integration_user_token(
    db: Session, user_id: UUID, integration: IntegrationIdentifier, token: str
):
    db.query(models.IntegrationUser).filter_by(
        user_id=user_id, integration=integration
    ).update({"auth_token": token})
    db.commit()


def get_integration_user(
    db: Session, integration: IntegrationIdentifier, user_id: UUID
) -> Optional[IntegrationUser]:
    db_integration_user = (
        db.query(models.IntegrationUser)
        .filter_by(user_id=user_id, integration=integration)
        .one_or_none()
    )
    if db_integration_user is None:
        return None
    return IntegrationUser.from_orm(db_integration_user)


def get_integration_config(
    db: Session, integration: IntegrationIdentifier, user_id: UUID
) -> Optional[IntegrationConfig]:
    user = get_integration_user(db, integration, user_id)
    if user is None:
        return None
    return get_integration_config_from_integration_user(user)


def get_integration_user_profile(
    db: Session, integration: IntegrationIdentifier, user_id: UUID
) -> Optional[IntegrationUserProfile]:
    user = get_integration_user(db, integration, user_id)
    if user is None:
        return None
    return IntegrationUserProfile.from_orm(user)


def update_integration_config(
    db: Session, user_id: UUID, config: IntegrationConfig
) -> Optional[models.IntegrationUser]:
    db_integration_user = (
        db.query(models.IntegrationUser)
        .filter_by(user_id=user_id, integration=config.integration)
        .one_or_none()
    )
    if db_integration_user is None:
        return None
    db_integration_user.active = config.active
    db_integration_user.classes = config.dict()["classes"]
    db.commit()
    db.refresh(db_integration_user)
    return db_integration_user


def delete_user(db: Session, user_id: UUID):
    db_user = db.get(models.User, user_id)
    db.delete(db_user)
    db.commit()


def upsert_user_integration_sessions(
    db: Session,
    user_id: UUID,
    integration: IntegrationIdentifier,
    user_sessions: list[UserSession],
):
    # delete unconfirmed sessions
    db.execute(
        delete(models.Session).where(
            models.Session.user_id == user_id,
            models.Session.integration == integration,
            models.Session.status != SessionState.CONFIRMED,
        )
    )
    for s in user_sessions:
        db.merge(session_model_from_user_session(s))
    db.commit()


def get_user(db, user_id) -> Optional[models.User]:
    return db.query(models.User).filter_by(id=user_id).one_or_none()


def get_user_config_by_id(db, user_id) -> Optional[Config]:
    db_user = get_user(db, user_id)
    if db_user is None:
        return None
    return get_user_config(db, db_user)


def get_user_push_notification_subscriptions(
    db, user_id: UUID
) -> list[PushNotificationSubscription]:
    return [
        PushNotificationSubscription(
            endpoint=db_subscription.endpoint,
            keys=PushNotificationSubscriptionKeys(**db_subscription.keys),
        )
        for db_subscription in db.query(models.PushNotificationSubscription).filter_by(
            user_id=user_id
        )
    ]


def get_user_config(db, user: models.User) -> Config:
    return config_from_stored(
        user.id,
        UserPreferences(**user.preferences),
        get_user_push_notification_subscriptions(db, user.id),
        AdminConfig(**user.admin_config),
    )


def get_user_config_by_slack_id(db, slack_id) -> Optional[Config]:
    if slack_id is None:
        return None
    for u in db.query(models.User).all():
        user_config = get_user_config(db, u)
        config = user_config.config
        if config.notifications is None:
            continue
        if config.notifications.slack is None:
            continue
        if config.notifications.slack.user_id == slack_id:
            return user_config
    return None


def upsert_push_notification_subscription(
    db, user_id, subscription: PushNotificationSubscription
):
    db_subscription = (
        db.query(models.PushNotificationSubscription)
        .filter_by(user_id=user_id, endpoint=subscription.endpoint)
        .one_or_none()
    )
    if db_subscription is None:
        db_subscription = models.PushNotificationSubscription(
            user_id=user_id,
            endpoint=subscription.endpoint,
            keys=subscription.keys.dict(),
        )
        db.add(db_subscription)
    else:
        db_subscription.keys = subscription.keys
    db.commit()
    db.refresh(db_subscription)
    return db_subscription


def delete_push_notification_subscription(
    db, subscription: PushNotificationSubscription, user_id: Optional[UUID] = None
) -> bool:
    db_subscription_query = db.query(models.PushNotificationSubscription).filter_by(
        endpoint=subscription.endpoint,
        keys=subscription.keys.dict(),
    )
    if user_id is not None:
        db_subscription_query = db_subscription_query.filter_by(user_id=user_id)
    db_subscription = db_subscription_query.one_or_none()
    if db_subscription is None:
        return False
    db.delete(db_subscription)
    db.commit()
    return True


def verify_push_notification_subscription(
    db, user_id: UUID, subscription: PushNotificationSubscription
) -> bool:
    return (
        db.query(models.PushNotificationSubscription)
        .filter_by(
            user_id=user_id,
            endpoint=subscription.endpoint,
            keys=subscription.keys.dict(),
        )
        .one_or_none()
    ) is not None
