import enum
import uuid

from sqlalchemy import Boolean, Column, Enum, ForeignKey, String
from sqlalchemy.dialects.postgresql import JSONB, UUID

from rezervo.database.base_class import Base
from rezervo.schemas.config.user import IntegrationIdentifier


class User(Base):
    __tablename__ = "users"

    id = Column(UUID(as_uuid=True), primary_key=True, index=True, default=uuid.uuid4)
    name = Column(String, unique=True, nullable=False)
    jwt_sub = Column(String, nullable=True)
    cal_token = Column(String, nullable=False)
    preferences = Column(JSONB)
    admin_config = Column(JSONB)

    def __repr__(self):
        return f"<User (id='{self.id}' name='{self.name}' jwt_sub='{self.jwt_sub}' preferences={self.preferences} admin_config={self.admin_config})>"


class PushNotificationSubscription(Base):
    __tablename__ = "push_notification_subscriptions"

    user_id = Column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="cascade"), primary_key=True
    )
    endpoint = Column(String, primary_key=True)
    keys = Column(JSONB, nullable=False)

    def __repr__(self):
        return f"<PushNotificationSubscription (user_id='{self.user_id}' endpoint={self.endpoint})>"


class IntegrationUser(Base):
    __tablename__ = "integration_users"

    user_id = Column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="cascade"), primary_key=True
    )
    integration = Column(
        Enum(IntegrationIdentifier, name="integration"), primary_key=True
    )
    username = Column(String, nullable=False)
    password = Column(String, nullable=False)
    auth_token = Column(String, nullable=True)
    active = Column(Boolean, nullable=False, default=True)
    classes = Column(JSONB, nullable=False, default=[])

    def __repr__(self):
        return f"<IntegrationUser (user_id='{self.user_id}' integration='{self.integration}' username='{self.username}' active='{self.active}' classes={self.classes})>"


class SessionState(enum.Enum):
    CONFIRMED = "CONFIRMED"
    BOOKED = "BOOKED"
    WAITLIST = "WAITLIST"
    PLANNED = "PLANNED"
    UNKNOWN = "UNKNOWN"


class Session(Base):
    __tablename__ = "sessions"

    integration = Column(
        Enum(IntegrationIdentifier, name="integration"),
        nullable=False,
        primary_key=True,
    )
    class_id = Column(String, primary_key=True)
    user_id = Column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="cascade"), primary_key=True
    )
    status = Column(Enum(SessionState))
    class_data = Column(JSONB)

    def __repr__(self):
        return f"<Session (integration='{self.integration}' class_id='{self.class_id}' user_id='{self.user_id}' status='{self.status}' class_data={self.class_data})>"
