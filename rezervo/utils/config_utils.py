import pytz

from rezervo.schemas.config.user import Class
from rezervo.schemas.schedule import BaseRezervoClass


def class_config_recurrent_id(class_config: Class):
    return recurrent_class_id(
        class_config.activity_id,
        class_config.weekday,
        class_config.start_time.hour,
        class_config.start_time.minute,
    )


def rezervo_class_recurrent_id(_class: BaseRezervoClass):
    localized_start_time = _class.start_time.astimezone(
        pytz.timezone("Europe/Oslo")
    )  # TODO: clean this
    return recurrent_class_id(
        _class.activity.id,
        localized_start_time.weekday(),
        localized_start_time.hour,
        localized_start_time.minute,
    )


def recurrent_class_id(activity_id: str, weekday: int, hour: int, minute: int):
    return f"{activity_id}_{weekday}_{hour}_{minute}"
