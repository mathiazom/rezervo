import enum
import uuid
from datetime import datetime

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    DateTime,
    Enum,
    ForeignKey,
    SmallInteger,
    String,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

from rezervo.schemas.community import UserRelationship


class Base(DeclarativeBase):
    pass


class User(Base):
    __tablename__ = "users"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, index=True, default=uuid.uuid4
    )
    name: Mapped[str] = mapped_column(String, unique=True, nullable=False)
    jwt_sub: Mapped[str | None] = mapped_column(String, nullable=True)
    cal_token: Mapped[str] = mapped_column(String, nullable=False)
    preferences: Mapped[dict] = mapped_column(JSONB)
    admin_config: Mapped[dict] = mapped_column(JSONB)

    def __repr__(self):
        return (
            f"<User (id='{self.id}' name='{self.name}' jwt_sub='{self.jwt_sub}' preferences={self.preferences} "
            f"admin_config={self.admin_config})>"
        )


class PushNotificationSubscription(Base):
    __tablename__ = "push_notification_subscriptions"

    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="cascade"), primary_key=True
    )
    endpoint: Mapped[str] = mapped_column(String, primary_key=True)
    keys: Mapped[dict] = mapped_column(JSONB, nullable=False)
    last_used: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

    def __repr__(self):
        return (
            f"<PushNotificationSubscription (user_id='{self.user_id}' endpoint='{self.endpoint}' "
            f"last_used='{self.last_used.isoformat() if self.last_used is not None else None}')>"
        )


class ChainUser(Base):
    __tablename__ = "chain_users"

    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="cascade"), primary_key=True
    )
    chain: Mapped[str] = mapped_column(String, primary_key=True)
    username: Mapped[str] = mapped_column(String, nullable=False)
    password: Mapped[str] = mapped_column(String, nullable=False)
    auth_token: Mapped[str | None] = mapped_column(String, nullable=True)
    active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)

    def __repr__(self):
        return (
            f"<ChainUser (user_id='{self.user_id}' chain='{self.chain}' username='{self.username}' "
            f"active='{self.active}')>"
        )


class RecurringBooking(Base):
    __tablename__ = "recurring_bookings"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, index=True, default=uuid.uuid4
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="cascade"), nullable=False
    )
    chain_id: Mapped[str] = mapped_column(String, nullable=False)
    location_id: Mapped[str] = mapped_column(String, nullable=False)
    activity_id: Mapped[str] = mapped_column(String, nullable=False)
    weekday: Mapped[int] = mapped_column(
        SmallInteger,
        CheckConstraint("weekday >= 0 AND weekday <= 6", name="check_weekday_range"),
        nullable=False,
    )
    start_time_hour: Mapped[int] = mapped_column(
        SmallInteger,
        CheckConstraint(
            "start_time_hour >= 0 AND start_time_hour <= 23",
            name="check_start_time_hour_range",
        ),
        nullable=False,
    )
    start_time_minute: Mapped[int] = mapped_column(
        SmallInteger,
        CheckConstraint(
            "start_time_minute >= 0 AND start_time_minute <= 59",
            name="check_start_time_minute_range",
        ),
        nullable=False,
    )
    display_name: Mapped[str | None] = mapped_column(String, nullable=True)

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
    NOSHOW = "NOSHOW"
    UNKNOWN = "UNKNOWN"


class Session(Base):
    __tablename__ = "sessions"

    chain: Mapped[str] = mapped_column(
        String,
        nullable=False,
        primary_key=True,
    )
    class_id: Mapped[str] = mapped_column(String, primary_key=True)
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="cascade"), primary_key=True
    )
    status: Mapped[SessionState] = mapped_column(Enum(SessionState))
    class_data: Mapped[dict] = mapped_column(JSONB)

    def __repr__(self):
        return (
            f"<Session (chain='{self.chain}' class_id='{self.class_id}' user_id='{self.user_id}' "
            f"status='{self.status}' class_data={self.class_data})>"
        )


class SlackClassNotificationReceipt(Base):
    __tablename__ = "slack_class_notification_receipts"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, index=True, default=uuid.uuid4
    )
    slack_user_id: Mapped[str] = mapped_column(String, nullable=False)
    chain: Mapped[str] = mapped_column(String, nullable=False)
    class_id: Mapped[str] = mapped_column(String, nullable=False)
    channel_id: Mapped[str] = mapped_column(String, nullable=False)
    message_id: Mapped[str] = mapped_column(String, nullable=False)
    scheduled_reminder_id: Mapped[str | None] = mapped_column(String, nullable=True)
    expires_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)

    def __repr__(self):
        return (
            f"<SlackClassNotificationReceipt (id='{self.id}' user_id='{self.slack_user_id}' chain='{self.chain}' "
            f"class_id='{self.class_id}' channel_id='{self.channel_id}' message_id='{self.message_id}'' "
            f"scheduled_reminder_id='{self.scheduled_reminder_id}' "
            f"expires_at='{self.expires_at.isoformat() if self.expires_at is not None else None}')>"
        )


class UserRelation(Base):
    __tablename__ = "user_relations"
    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, index=True, default=uuid.uuid4
    )
    user_one: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="cascade"), primary_key=True
    )
    user_two: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="cascade"), primary_key=True
    )
    relationship: Mapped[UserRelationship] = mapped_column(Enum(UserRelationship))

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
