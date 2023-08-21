import json
import re
from typing import Optional
from uuid import UUID

import pydantic
from auth0.management import Auth0
from crontab import CronTab
from fastapi import FastAPI, status, Response, Request, BackgroundTasks, Depends, HTTPException
from fastapi.security import HTTPBearer
from icalendar import cal
from sqlalchemy.orm import Session

from sit_rezervo import models
from sit_rezervo.auth.auth0 import get_auth0_management_client
from sit_rezervo.schemas.booking import BookingPayload
from sit_rezervo.schemas.config.config import Config, config_from_stored, ConfigValue, read_app_config
from sit_rezervo.schemas.config.user import UserConfig, UserNameWithIsSelf
from sit_rezervo.auth.sit import AuthenticationError
from sit_rezervo.booking import find_class_by_id
from sit_rezervo.consts import SLACK_ACTION_ADD_BOOKING_TO_CALENDAR, SLACK_ACTION_CANCEL_BOOKING
from sit_rezervo.database.database import SessionLocal
from sit_rezervo.errors import BookingError
from sit_rezervo.main import try_cancel_booking, try_authenticate, pull_sessions, try_book_class
from sit_rezervo.notify.slack import notify_cancellation_slack, notify_working_slack, \
    notify_cancellation_failure_slack, show_unauthorized_action_modal_slack
from sit_rezervo.schemas.schedule import SitClass
from sit_rezervo.schemas.session import UserNameSessionStatus
from sit_rezervo.settings import Settings, get_settings
from sit_rezervo.database import crud
from sit_rezervo.notify.slack import delete_scheduled_dm_slack, verify_slack_request
from sit_rezervo.schemas.config.stored import StoredConfig
from sit_rezervo.types import CancelBookingActionValue, Interaction
from sit_rezervo.utils.config_utils import class_config_recurrent_id
from sit_rezervo.utils.cron_utils import build_cron_comment_prefix_for_config, build_cron_jobs_from_config, \
    upsert_jobs_by_comment
from sit_rezervo.utils.ical_utils import ical_event_from_sit_class_session

api = FastAPI()

# Scheme for the Authorization header
token_auth_scheme = HTTPBearer()


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def find_config_by_slack_id(configs: list[ConfigValue], user_id: str) -> Optional[ConfigValue]:
    for config in configs:
        if config.notifications is None or config.notifications.slack is None:
            continue
        if config.notifications.slack.user_id == user_id:
            return config
    return None


def handle_cancel_booking_slack_action(config: ConfigValue, action_value: CancelBookingActionValue, message_ts: str,
                                       response_url: str):
    if config.notifications is None:
        print("[WARNING] Notifications config not specified, no notifications will be sent!")
        slack_config = None
    else:
        slack_config = config.notifications.slack
        if slack_config is None:
            print("[WARNING] Slack notifications config not specified, no Slack notifications will be sent!")
        else:
            notify_working_slack(slack_config.bot_token, slack_config.channel_id, message_ts)
    print("[INFO] Authenticating...")
    auth_result = try_authenticate(config.auth.email, config.auth.password,
                                   config.auth.max_attempts)
    if isinstance(auth_result, AuthenticationError):
        print("[ERROR] Authentication failed, abort!")
        if slack_config is not None:
            notify_cancellation_failure_slack(slack_config.bot_token, slack_config.channel_id, message_ts, auth_result)
        return
    _class = find_class_by_id(auth_result, action_value.class_id)
    if _class is None:
        print("[ERROR] Class retrieval by id failed, abort!")
        if slack_config is not None:
            notify_cancellation_failure_slack(slack_config.bot_token, slack_config.channel_id, message_ts,
                                              BookingError.CLASS_MISSING)
        return
    cancellation_error = try_cancel_booking(auth_result, _class, config.booking.max_attempts)
    if cancellation_error is not None:
        if slack_config is not None:
            notify_cancellation_failure_slack(slack_config.bot_token, slack_config.channel_id, message_ts,
                                              cancellation_error)
        return
    if slack_config is not None:
        if action_value.scheduled_reminder_id is not None:
            delete_scheduled_dm_slack(slack_config.bot_token, slack_config.user_id, action_value.scheduled_reminder_id)
        notify_cancellation_slack(slack_config.bot_token, slack_config.channel_id, message_ts, response_url)
    pull_sessions()


@api.post("/slackinteraction")
async def slack_action(request: Request, background_tasks: BackgroundTasks, db: Session = Depends(get_db)):
    raw_body = await request.body()  # must read body before retrieving form data
    payload = (await request.form())["payload"]
    interaction: Interaction = pydantic.parse_raw_as(type_=Interaction, b=payload)
    if interaction.type != "block_actions":
        return Response(f"Unsupported interaction type '{interaction.type}'", status_code=status.HTTP_400_BAD_REQUEST)
    if len(interaction.actions) != 1:
        return Response(f"Unsupported number of interaction actions", status_code=status.HTTP_400_BAD_REQUEST)
    action = interaction.actions[0]
    if action.action_id == SLACK_ACTION_ADD_BOOKING_TO_CALENDAR:
        return Response(status_code=status.HTTP_200_OK)
    if action.action_id == SLACK_ACTION_CANCEL_BOOKING:
        configs: list[ConfigValue] = [config_from_stored(StoredConfig.from_orm(c)).config for c in
                                      db.query(models.Config).all()]
        if configs is None:
            print("[ERROR] No configs available, abort!")
            return Response(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR)
        action_value = CancelBookingActionValue(**json.loads(action.value))
        config = find_config_by_slack_id(configs, action_value.user_id)
        if config is None:
            print("[ERROR] Could not find config for Slack user, abort!")
            return Response(status_code=status.HTTP_400_BAD_REQUEST)
        if config.notifications is None \
                or config.notifications.slack is None \
                or not verify_slack_request(raw_body, request.headers,
                                            config.notifications.slack.signing_secret):
            return Response(f"Authentication failed", status_code=status.HTTP_401_UNAUTHORIZED)
        # This check should be performed before retrieving config, but then we wouldn't be able to display a funny modal
        if action_value.user_id != interaction.user.id:
            print("[WARNING] Detected cancellation attempt by an unauthorized user")
            if config.notifications is not None and config.notifications.slack is not None:
                background_tasks.add_task(show_unauthorized_action_modal_slack,
                                          config.notifications.slack.bot_token,
                                          interaction.trigger_id)
            return Response("Nice try 👏", status_code=status.HTTP_403_FORBIDDEN)
        message_ts = interaction.container.message_ts
        background_tasks.add_task(handle_cancel_booking_slack_action, config, action_value, message_ts,
                                  interaction.response_url)
        return Response(status_code=status.HTTP_200_OK)
    return Response(f"Unsupported interaction action", status_code=status.HTTP_400_BAD_REQUEST)


@api.post("/book")
async def book_class(payload: BookingPayload, token=Depends(token_auth_scheme), db: Session = Depends(get_db),
                     settings: Settings = Depends(get_settings)):
    db_user = crud.user_from_token(db, settings, token)
    if db_user is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Not authenticated")
    config = config_from_stored(StoredConfig.from_orm(crud.get_user_config(db, db_user.id))).config
    print("[INFO] Authenticating...")
    booking_token = try_authenticate(config.auth.email, config.auth.password,
                                     config.auth.max_attempts)
    if isinstance(booking_token, AuthenticationError):
        print("[ERROR] Authentication failed, abort!")
        return Response(status_code=status.HTTP_401_UNAUTHORIZED, content="Authentication failed for sit.no")
    _class = find_class_by_id(booking_token, payload.class_id)
    if _class is None:
        print("[ERROR] Class retrieval by id failed, abort!")
        return Response(status_code=status.HTTP_404_NOT_FOUND, content="Class not found for given class id")
    booking_result = try_book_class(booking_token, _class, config.booking.max_attempts, config.notifications)
    if booking_result is not None:
        return Response(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR)
    pull_sessions(db_user.id)


@api.post("/cancelBooking")
def cancel_booking(payload: BookingPayload, token=Depends(token_auth_scheme), db: Session = Depends(get_db),
                   settings: Settings = Depends(get_settings)):
    # TODO: add Slack notifications
    db_user = crud.user_from_token(db, settings, token)
    if db_user is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Not authenticated")
    config = config_from_stored(StoredConfig.from_orm(crud.get_user_config(db, db_user.id))).config
    print("[INFO] Authenticating...")
    cancellation_token = try_authenticate(config.auth.email, config.auth.password,
                                          config.auth.max_attempts)
    if isinstance(cancellation_token, AuthenticationError):
        print("[ERROR] Authentication failed, abort!")
        return Response(status_code=status.HTTP_401_UNAUTHORIZED, content="Authentication failed for sit.no")
    _class = find_class_by_id(cancellation_token, payload.class_id)
    if _class is None:
        print("[ERROR] Class retrieval by id failed, abort!")
        return Response(status_code=status.HTTP_404_NOT_FOUND, content="Class not found for given class id")
    cancellation_error = try_cancel_booking(cancellation_token, _class, config.booking.max_attempts)
    if cancellation_error is not None:
        return Response(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR)
    pull_sessions(db_user.id)


def upsert_booking_crontab(config: Config, user: models.User):
    with CronTab(user=True) as crontab:
        upsert_jobs_by_comment(
            crontab,
            re.compile(f'^{build_cron_comment_prefix_for_config(config.id)}.*$'),
            build_cron_jobs_from_config(config, user)
        )


def delete_booking_crontab(config_id: UUID):
    with CronTab(user=True) as crontab:
        upsert_jobs_by_comment(
            crontab,
            re.compile(f'^{build_cron_comment_prefix_for_config(config_id)}.*$'),
            []
        )


@api.get("/config", response_model=UserConfig)
def get_user_config(token=Depends(token_auth_scheme), db: Session = Depends(get_db),
                    settings: Settings = Depends(get_settings)):
    db_user = crud.user_from_token(db, settings, token)
    if db_user is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Not authenticated")
    db_config = crud.get_user_config(db, db_user.id)
    if db_config is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND)
    return db_config.config


@api.put("/config", response_model=UserConfig)
def upsert_user_config(user_config: UserConfig, background_tasks: BackgroundTasks, token=Depends(token_auth_scheme),
                       db: Session = Depends(get_db), settings: Settings = Depends(get_settings)):
    db_user = crud.user_from_token(db, settings, token)
    if db_user is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Not authenticated")
    db_config = crud.update_user_config(db, db_user.id, user_config)
    if db_config is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND)
    stored_config = StoredConfig.from_orm(db_config)
    config = config_from_stored(stored_config)
    background_tasks.add_task(upsert_booking_crontab, config, db_user)
    background_tasks.add_task(pull_sessions, db_user.id)
    return db_config.config


@api.get("/all_configs", response_model=dict[str, list[UserNameWithIsSelf]])
def get_all_configs_index(token=Depends(token_auth_scheme), db: Session = Depends(get_db),
                          settings: Settings = Depends(get_settings),
                          auth0_mgmt_client: Auth0 = Depends(get_auth0_management_client)):
    db_user = crud.user_from_token(db, settings, token)
    if db_user is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Not authenticated")
    db_users: list[models.User] = db.query(models.User).all()
    user_name_lookup = {u.id: auth0_mgmt_client.users.get(u.jwt_sub)["name"] for u in db_users}
    user_configs_dict = {}
    for dbu in db_users:
        db_user_config: Optional[models.Config] = db.query(models.Config).filter_by(user_id=dbu.id).one_or_none()
        if db_user_config is None:
            continue
        user_config = StoredConfig.from_orm(db_user_config).config
        if not user_config.active:
            continue
        for c in user_config.classes:
            class_id = class_config_recurrent_id(c)
            if class_id not in user_configs_dict:
                user_configs_dict[class_id] = []
            user_configs_dict[class_id].append(UserNameWithIsSelf(
                is_self=dbu.id == db_user.id,
                user_name=user_name_lookup[dbu.id]
            ))
    return user_configs_dict


@api.get("/sessions", response_model=dict[str, list[UserNameSessionStatus]])
def get_sessions_index(
        token=Depends(token_auth_scheme),
        db: Session = Depends(get_db),
        settings: Settings = Depends(get_settings),
        auth0_mgmt_client: Auth0 = Depends(get_auth0_management_client)):
    db_user = crud.user_from_token(db, settings, token)
    if db_user is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Not authenticated")
    user_name_lookup = {u.id: auth0_mgmt_client.users.get(u.jwt_sub)["name"] for u in db.query(models.User).all()}
    session_dict = {}
    for session in db.query(models.Session).filter(models.Session.status != models.SessionState.PLANNED).all():
        class_id = session.class_id
        if class_id not in session_dict:
            session_dict[class_id] = []
        session_dict[class_id].append(UserNameSessionStatus(
            is_self=session.user_id == db_user.id,
            user_name=user_name_lookup[session.user_id],
            status=session.status
        ))
    return session_dict


@api.get("/cal_token", response_model=str)
def get_calendar_token(token=Depends(token_auth_scheme), db: Session = Depends(get_db),
                       settings: Settings = Depends(get_settings)):
    db_user = crud.user_from_token(db, settings, token)
    if db_user is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Not authenticated")
    return db_user.cal_token


@api.get("/cal")
def get_calendar(token: str, include_past: bool = True, db: Session = Depends(get_db)):
    db_user = db.query(models.User).filter_by(cal_token=token).one_or_none()
    if db_user is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Not authenticated")
    sessions_query = db.query(models.Session).filter_by(user_id=db_user.id)
    if not include_past:
        sessions_query = sessions_query.filter(models.Session.status != models.SessionState.CONFIRMED)
    sessions = [s for s in sessions_query.all() if s.class_data is not None]
    ical = cal.Calendar()
    ical.add('prodid', '-//rezervo//rezervo.no//')
    ical.add('version', '2.0')
    ical.add('method', 'PUBLISH')
    ical.add('calscale', 'GREGORIAN')
    ical.add('x-wr-timezone', read_app_config().booking.timezone)
    ical.add('x-wr-calname', f'rezervo')
    ical.add(
        'x-wr-caldesc',
        f'Planlagte{" og gjennomførte" if include_past else ""} timer for {db_user.name} (rezervo.no)'
    )
    for s in sessions:
        ical.add_component(ical_event_from_sit_class_session(s))
    return Response(content=ical.to_ical(), media_type='text/calendar')
