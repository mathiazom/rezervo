import enum
import uuid

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    Column,
    DateTime,
    Enum,
    ForeignKey,
    SmallInteger,
    String,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID

from rezervo.database.base_class import Base
from rezervo.schemas.community import UserRelationship


class User(Base):
    __tablename__ = "users"

    id = Column(UUID(as_uuid=True), primary_key=True, index=True, default=uuid.uuid4)
    name = Column(String, unique=True, nullable=False)
    jwt_sub = Column(String, nullable=True)
    cal_token = Column(String, nullable=False)
    preferences = Column(JSONB)
    admin_config = Column(JSONB)

    def __repr__(self):
        return (
            f"<User (id='{self.id}' name='{self.name}' jwt_sub='{self.jwt_sub}' preferences={self.preferences} "
            f"admin_config={self.admin_config})>"
        )


class PushNotificationSubscription(Base):
    __tablename__ = "push_notification_subscriptions"

    user_id = Column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="cascade"), primary_key=True
    )
    endpoint = Column(String, primary_key=True)
    keys = Column(JSONB, nullable=False)
    last_used = Column(DateTime, nullable=True)

    def __repr__(self):
        return (
            f"<PushNotificationSubscription (user_id='{self.user_id}' endpoint='{self.endpoint}' "
            f"last_used='{self.last_used.isoformat() if self.last_used is not None else None}')>"
        )


class ChainUser(Base):
    __tablename__ = "chain_users"

    user_id = Column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="cascade"), primary_key=True
    )
    chain = Column(String, primary_key=True)
    username = Column(String, nullable=False)
    password = Column(String, nullable=False)
    auth_token = Column(String, nullable=True)
    active = Column(Boolean, nullable=False, default=True)

    def __repr__(self):
        return (
            f"<ChainUser (user_id='{self.user_id}' chain='{self.chain}' username='{self.username}' "
            f"active='{self.active}')>"
        )


class RecurringBooking(Base):
    __tablename__ = "recurring_bookings"

    id = Column(UUID(as_uuid=True), primary_key=True, index=True, default=uuid.uuid4)
    user_id = Column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="cascade"), nullable=False
    )
    chain_id = Column(String, nullable=False)
    location_id = Column(String, nullable=False)
    activity_id = Column(String, nullable=False)
    weekday = Column(
        SmallInteger,
        CheckConstraint("weekday >= 0 AND weekday <= 6", name="check_weekday_range"),
        nullable=False,
    )
    start_time_hour = Column(
        SmallInteger,
        CheckConstraint(
            "start_time_hour >= 0 AND start_time_hour <= 23",
            name="check_start_time_hour_range",
        ),
        nullable=False,
    )
    start_time_minute = Column(
        SmallInteger,
        CheckConstraint(
            "start_time_minute >= 0 AND start_time_minute <= 59",
            name="check_start_time_minute_range",
        ),
        nullable=False,
    )
    display_name = Column(String, nullable=True)

    __table_args__ = (
        UniqueConstraint(
            "user_id",
            "chain_id",
            "location_id",
            "activity_id",
            "weekday",
            "start_time_hour",
            "start_time_minute",
            name="unique_recurring_booking",
        ),
    )


class SessionState(enum.Enum):
    CONFIRMED = "CONFIRMED"
    BOOKED = "BOOKED"
    WAITLIST = "WAITLIST"
    PLANNED = "PLANNED"
    UNKNOWN = "UNKNOWN"


class Session(Base):
    __tablename__ = "sessions"

    chain = Column(
        String,
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
        return (
            f"<Session (chain='{self.chain}' class_id='{self.class_id}' user_id='{self.user_id}' "
            f"status='{self.status}' class_data={self.class_data})>"
        )


class SlackClassNotificationReceipt(Base):
    __tablename__ = "slack_class_notification_receipts"

    id = Column(UUID(as_uuid=True), primary_key=True, index=True, default=uuid.uuid4)
    slack_user_id = Column(String, nullable=False)
    chain = Column(String, nullable=False)
    class_id = Column(String, nullable=False)
    channel_id = Column(String, nullable=False)
    message_id = Column(String, nullable=False)
    scheduled_reminder_id = Column(String, nullable=True)
    expires_at = Column(DateTime, nullable=False)

    def __repr__(self):
        return (
            f"<SlackClassNotificationReceipt (id='{self.id}' user_id='{self.slack_user_id}' chain='{self.chain}' "
            f"class_id='{self.class_id}' channel_id='{self.channel_id}' message_id='{self.message_id}'' "
            f"scheduled_reminder_id='{self.scheduled_reminder_id}' "
            f"expires_at='{self.expires_at.isoformat() if self.expires_at is not None else None}')>"
        )


class UserRelation(Base):
    __tablename__ = "user_relations"
    id = Column(UUID(as_uuid=True), primary_key=True, index=True, default=uuid.uuid4)
    user_one = Column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="cascade"), primary_key=True
    )
    user_two = Column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="cascade"), primary_key=True
    )
    relationship = Column(Enum(UserRelationship))

    __table_args__ = (
        UniqueConstraint(
            "user_one",
            "user_two",
            name="unique_user_relation",
        ),
    )

    def __repr__(self):
        return (
            f"<UserRelation (user_one='{self.user_one}' user_two='{self.user_two}' "
            f"relationship='{self.relationship}')>"
        )
