from typing import Optional
from uuid import UUID

from rich import print as rprint

from rezervo import models
from rezervo.active_integrations import ACTIVE_INTEGRATIONS
from rezervo.database import crud
from rezervo.database.database import SessionLocal
from rezervo.schemas.config.user import IntegrationIdentifier
from rezervo.utils.cron_utils import upsert_booking_crontab
from rezervo.utils.logging_utils import err


def refresh_cron(
    user_id: Optional[UUID] = None,
    integrations: list[IntegrationIdentifier] = ACTIVE_INTEGRATIONS.keys(),
):
    with SessionLocal() as db:
        users_query = db.query(models.User)
        if user_id is not None:
            users_query = users_query.filter_by(id=user_id)
        for u in users_query.all():
            config = crud.get_user_config_by_id(db, u.id)
            if config is None:
                err.log(f"User '{u.name}' has no config, skipping...")
                continue
            for i in integrations:
                ic = crud.get_integration_config(db, i, u.id)
                if ic is not None:
                    upsert_booking_crontab(config, ic, u)
                    rprint(f"✔ '{i.name}' crontab updated for '{u.name}'")
