"""session_class_data_location_type_fix

Revision ID: 6133793acba4
Revises: a959d99283df
Create Date: 2024-04-22 10:26:14.592487

"""

import enum
import uuid
from typing import Optional

import sqlalchemy as sa
from alembic import op
from sqlalchemy import (
    Enum,
    ForeignKey,
    SmallInteger,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

from rezervo.schemas.community import UserRelationship
from rezervo.utils.typing_utils import small_integer

# revision identifiers, used by Alembic.
revision = "6133793acba4"
down_revision = "a959d99283df"
branch_labels = None
depends_on = None


class SessionState(enum.Enum):
    CONFIRMED = "CONFIRMED"
    BOOKED = "BOOKED"
    WAITLIST = "WAITLIST"
    PLANNED = "PLANNED"
    NOSHOW = "NOSHOW"
    UNKNOWN = "UNKNOWN"


class Base(DeclarativeBase):
    type_annotation_map = {
        uuid.UUID: UUID(as_uuid=True),
        dict: JSONB,
        small_integer: SmallInteger,
        SessionState: Enum(SessionState),
        UserRelationship: Enum(UserRelationship),
    }


class User(Base):
    __tablename__ = "users"

    id: Mapped[uuid.UUID] = mapped_column(
        primary_key=True, index=True, default=uuid.uuid4
    )
    name: Mapped[str] = mapped_column(unique=True)
    jwt_sub: Mapped[Optional[str]] = mapped_column()
    cal_token: Mapped[str] = mapped_column()
    preferences: Mapped[dict] = mapped_column()
    admin_config: Mapped[dict] = mapped_column()


class Session(Base):
    __tablename__ = "sessions"

    chain: Mapped[str] = mapped_column(
        primary_key=True,
    )
    class_id: Mapped[str] = mapped_column(primary_key=True)
    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="cascade"), primary_key=True
    )
    status: Mapped[SessionState] = mapped_column()
    class_data: Mapped[dict] = mapped_column()


def upgrade() -> None:
    # ### commands auto generated by Alembic - please adjust! ###
    session = sa.orm.Session(bind=op.get_bind())
    for s in session.query(Session):
        s.class_data = {
            **s.class_data,
            "location": {
                **s.class_data["location"],
                "id": str(s.class_data["location"]["id"]),
            },
        }
    session.commit()
    # ### end Alembic commands ###


def downgrade() -> None:
    # ### commands auto generated by Alembic - please adjust! ###
    session = sa.orm.Session(bind=op.get_bind())
    for s in session.query(Session):
        try:
            s.class_data = {
                **s.class_data,
                "location": {
                    **s.class_data["location"],
                    "id": int(s.class_data["location"]["id"]),
                },
            }
        except ValueError:
            pass
    session.commit()
    # ### end Alembic commands ###
