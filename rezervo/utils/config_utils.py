from rezervo.schemas.config.user import Class


def class_config_recurrent_id(class_config: Class):
    return recurrent_class_id(
        class_config.activity_id,
        class_config.weekday,
        class_config.start_time.hour,
        class_config.start_time.minute,
    )


def recurrent_class_id(activity_id: str, weekday: int, hour: int, minute: int):
    return f"{activity_id}_{weekday}_{hour}_{minute}"
