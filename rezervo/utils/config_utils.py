from rezervo.schemas.config.config import Class


def class_config_recurrent_id(class_config: Class):
    return recurrent_class_id(
        class_config.activity,
        class_config.weekday,
        class_config.time.hour,
        class_config.time.minute,
    )


def recurrent_class_id(activity_id: int, weekday: int, hour: int, minute: int):
    return f"{activity_id}_{weekday}_{hour}_{minute}"
