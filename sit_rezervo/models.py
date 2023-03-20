import uuid

from sqlalchemy import Column, String, ForeignKey
from sqlalchemy.dialects.postgresql import UUID, JSONB

from sit_rezervo.database.base_class import Base

class User(Base):
    __tablename__ = "users"

    id = Column(UUID(as_uuid=True), primary_key=True, index=True, default=uuid.uuid4)
    name = Column(String)
    jwt_sub = Column(String, nullable=True)


class Config(Base):
    __tablename__ = "configs"

    id = Column(UUID(as_uuid=True), primary_key=True, index=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="cascade"), unique=True)
    config = Column(JSONB)
    admin_config = Column(JSONB)

    def __repr__(self):
        return f"<Config (id='{self.id}' user_id='{self.user_id}' config={self.config} admin_config={self.admin_config})>"
