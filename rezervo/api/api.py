from fastapi import (
    FastAPI,
)

from rezervo.api import (
    booking,
    cal,
    community,
    features,
    integration_config,
    preferences,
    sessions,
    slack,
)
from rezervo.api.notifications import push

api = FastAPI()
api.include_router(integration_config.router, tags=["integration config"])
api.include_router(preferences.router, tags=["preferences"])
api.include_router(push.router, tags=["notifications"])
api.include_router(booking.router, tags=["booking"])
api.include_router(sessions.router, tags=["sessions"])
api.include_router(cal.router, tags=["calendar"])
api.include_router(slack.router, tags=["slack"])
api.include_router(features.router, tags=["features"])
api.include_router(community.router, tags=["community"])
