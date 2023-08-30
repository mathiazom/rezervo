from rich import print as rprint

from rezervo import models
from rezervo.database import crud
from rezervo.database.database import SessionLocal
from rezervo.integrations.active import ACTIVE_INTEGRATIONS
from rezervo.utils.cron_utils import upsert_booking_crontab


def refresh_cron():
    with SessionLocal() as db:
        for u in db.query(models.User).all():
            config = crud.get_user_config_by_id(db, u.id)
            for i in ACTIVE_INTEGRATIONS.keys():
                ic = crud.get_integration_config(db, i, u.id)
                if ic is not None:
                    upsert_booking_crontab(config, ic, u)
    rprint("✔ Crontab updated")
