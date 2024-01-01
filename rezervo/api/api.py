from fastapi import (
    FastAPI,
)

from rezervo.api import (
    booking,
    cal,
    chain_config,
    chains,
    features,
    preferences,
    schedules,
    sessions,
    slack,
)
from rezervo.api.notifications import push

api = FastAPI()
api.include_router(chains.router, tags=["chains"])
api.include_router(schedules.router, tags=["schedules"])
api.include_router(chain_config.router, tags=["chain config"])
api.include_router(preferences.router, tags=["preferences"])
api.include_router(features.router, tags=["features"])
api.include_router(booking.router, tags=["booking"])
api.include_router(sessions.router, tags=["sessions"])
api.include_router(cal.router, tags=["calendar"])
api.include_router(push.router, tags=["notifications"])
api.include_router(slack.router, tags=["slack"])
