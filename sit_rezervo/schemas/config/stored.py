from uuid import UUID

from sit_rezervo.schemas.base import OrmBase
from sit_rezervo.schemas.config.admin import AdminConfig
from sit_rezervo.schemas.config.user import UserConfig


class StoredConfig(OrmBase):
    id: UUID
    user_id: UUID
    config: UserConfig
    admin_config: AdminConfig
