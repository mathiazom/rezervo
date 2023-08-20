import uuid
import enum

from sqlalchemy import Enum, Column, String, ForeignKey
from sqlalchemy.dialects.postgresql import UUID, JSONB

from sit_rezervo.database.base_class import Base


class User(Base):
    __tablename__ = "users"

    id = Column(UUID(as_uuid=True), primary_key=True, index=True, default=uuid.uuid4)
    name = Column(String)
    jwt_sub = Column(String, nullable=True)
    cal_token = Column(String, nullable=False)


class Config(Base):
    __tablename__ = "configs"

    id = Column(UUID(as_uuid=True), primary_key=True, index=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="cascade"), unique=True)
    config = Column(JSONB)
    admin_config = Column(JSONB)

    def __repr__(self):
        return f"<Config (id='{self.id}' user_id='{self.user_id}' config={self.config} admin_config={self.admin_config})>"


class SessionState(enum.Enum):
    CONFIRMED = "CONFIRMED"
    BOOKED = "BOOKED"
    WAITLIST = "WAITLIST"
    PLANNED = "PLANNED"
    UNKNOWN = "UNKNOWN"


class Session(Base):
    __tablename__ = "sessions"

    class_id = Column(String, primary_key=True)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="cascade"), primary_key=True)
    status = Column(Enum(SessionState))
    class_data = Column(JSONB)

    def __repr__(self):
        return f"<Session (class_id='{self.class_id}' user_id='{self.user_id}' status='{self.status}' class_data={self.class_data})>"
