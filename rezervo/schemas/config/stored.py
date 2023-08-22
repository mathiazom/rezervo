from uuid import UUID

from rezervo.schemas.base import OrmBase
from rezervo.schemas.config.admin import AdminConfig
from rezervo.schemas.config.user import UserConfig


class StoredConfig(OrmBase):
    id: UUID
    user_id: UUID
    config: UserConfig
    admin_config: AdminConfig
