from fastapi import APIRouter, Depends, HTTPException
from icalendar import cal  # type: ignore[import-untyped]
from sqlalchemy.orm import Session
from starlette import status
from starlette.responses import Response

from rezervo import models
from rezervo.api.common import get_db, token_auth_scheme
from rezervo.database import crud
from rezervo.schemas.config.app import AppConfig
from rezervo.schemas.config.config import read_app_config
from rezervo.schemas.schedule import UserSession
from rezervo.utils.ical_utils import ical_event_from_session

router = APIRouter()


@router.get("/cal-token", response_model=str)
def get_calendar_token(
    token=Depends(token_auth_scheme),
    db: Session = Depends(get_db),
    app_config: AppConfig = Depends(read_app_config),
):
    db_user = crud.user_from_token(db, app_config, token)
    if db_user is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED)
    return db_user.cal_token


@router.get("/cal")
def get_calendar(
    token: str,
    include_past: bool = True,
    db: Session = Depends(get_db),
    app_config: AppConfig = Depends(read_app_config),
):
    db_user = db.query(models.User).filter_by(cal_token=token).one_or_none()
    if db_user is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED)
    sessions_query = (
        db.query(models.Session)
        .filter_by(user_id=db_user.id)
        .filter(
            ~models.Session.status.in_(
                [models.SessionState.UNKNOWN, models.SessionState.NOSHOW]
            )
        )
    )
    if not include_past:
        sessions_query = sessions_query.filter(
            models.Session.status != models.SessionState.CONFIRMED
        )
    timezone = read_app_config().booking.timezone
    ical = cal.Calendar()
    ical.add("prodid", "-//rezervo//rezervo.no//")
    ical.add("version", "2.0")
    ical.add("method", "PUBLISH")
    ical.add("calscale", "GREGORIAN")
    ical.add("x-wr-timezone", timezone)
    ical.add("x-wr-calname", "rezervo")
    ical.add(
        "x-wr-caldesc",
        f'Planlagte{" og gjennomførte" if include_past else ""} timer for {db_user.name} (rezervo.no)',
    )
    for s in sessions_query.all():
        if s.class_data is None:
            continue
        event = ical_event_from_session(
            UserSession.from_orm(s), timezone, app_config.web_host
        )
        if event is not None:
            ical.add_component(event)
    return Response(content=ical.to_ical(), media_type="text/calendar")
