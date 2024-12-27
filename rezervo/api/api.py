from fastapi import (
    FastAPI,
)
from fastapi.middleware.cors import CORSMiddleware
from starlette.staticfiles import StaticFiles

from rezervo.api import (
    activity_categories,
    booking,
    cal,
    chain_config,
    chains,
    community,
    features,
    preferences,
    schedules,
    sessions,
    slack,
    user,
    webhooks,
)
from rezervo.api.notifications import push
from rezervo.http_client import HttpClient
from rezervo.schemas.config.config import read_app_config

api = FastAPI(
    on_startup=[HttpClient.singleton], on_shutdown=[HttpClient.close_singleton]
)

api.add_middleware(
    CORSMiddleware,
    allow_origins=read_app_config().allowed_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

api.mount("/images", StaticFiles(directory="rezervo/static"), name="images")

api.include_router(chains.router, tags=["chains"])
api.include_router(schedules.router, tags=["schedules"])
api.include_router(activity_categories.router, tags=["activity categories"])
api.include_router(chain_config.router, tags=["chain config"])
api.include_router(preferences.router, tags=["preferences"])
api.include_router(features.router, tags=["features"])
api.include_router(booking.router, tags=["booking"])
api.include_router(sessions.router, tags=["sessions"])
api.include_router(cal.router, tags=["calendar"])
api.include_router(push.router, tags=["notifications"])
api.include_router(slack.router, tags=["slack"])
api.include_router(user.router, tags=["user"])
api.include_router(community.router, tags=["community"])
api.include_router(webhooks.router, tags=["webhooks"])
