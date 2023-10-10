from typing import Optional
from uuid import UUID

from rezervo.database import crud
from rezervo.database.database import SessionLocal
from rezervo.integrations.active import ACTIVE_INTEGRATIONS, get_integration
from rezervo.schemas.config.user import IntegrationIdentifier


def pull_integration_sessions(
    integration: IntegrationIdentifier, user_id: Optional[UUID] = None
):
    sessions = get_integration(integration).fetch_sessions(user_id)
    with SessionLocal() as db:
        for uid, user_sessions in sessions.items():
            crud.upsert_user_integration_sessions(db, uid, integration, user_sessions)


def pull_sessions(
    integration: Optional[IntegrationIdentifier] = None, user_id: Optional[UUID] = None
):
    if integration is not None:
        pull_integration_sessions(integration, user_id)
        return
    for i in ACTIVE_INTEGRATIONS.keys():
        pull_integration_sessions(i, user_id)
