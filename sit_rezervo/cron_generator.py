import datetime

from sit_rezervo.config import Class, Cron

STARTUP_DAYS_BEFORE_ACTIVITY = 2


def generate_booking_cron_job(index: int, _class: Class, cron_config: Cron, config_path: str) -> str:
    # Using current datetime simply as a starting point
    # We really only care about the "wall clock" part, which is replaced by input values
    activity_time = datetime.datetime.now().replace(
        hour=_class.time.hour,
        minute=_class.time.minute,
        second=0, microsecond=0  # Cosmetic only
    )
    # print(f"[INFO] Activity starts on weekday {_class.weekday} (cron weekday {(_class.weekday + 1) % 7}) "
    #       f"at {activity_time.time()}")

    # Back up time to give booking script some prep time
    booking_time = activity_time - datetime.timedelta(minutes=cron_config.preparation_minutes)
    # Handle case where backing up time changes the weekday
    booking_weekday_delta = activity_time.weekday() - booking_time.weekday()

    booking_weekday = (_class.weekday + 1 - STARTUP_DAYS_BEFORE_ACTIVITY - booking_weekday_delta) % 7

    # print(f"[INFO] Creating booking cron job at '{booking_time.minute} {booking_time.hour} * * {booking_weekday}' "
    #       f"({cron_config.preparation_minutes} minutes before booking opens)")

    program_command = f"cd {cron_config.sit_rezervo_dir} || exit 1; PATH=$PATH:/usr/local/bin " \
                      f"{cron_config.python_path}/sit-rezervo book -c {config_path}"
    output_redirection = f">> {cron_config.log_path} 2>&1"

    class_name = _class.display_name if _class.display_name is not None else _class.activity

    booking_cron_job = (
        f"# {class_name}\n"
        f"{booking_time.minute} {booking_time.hour} * * {booking_weekday} "
        f"{program_command} {index} "
        f"{output_redirection}"
        "\n"
    )

    if cron_config.precheck_hours is not None:
        precheck_time = booking_time - datetime.timedelta(hours=cron_config.precheck_hours)
        precheck_weekday = booking_weekday
        # print(f"[INFO] Creating precheck cron job at '{precheck_time.minute} {precheck_time.hour} * * "
        #       f"{precheck_weekday}' ({cron_config.precheck_hours} hours before booking)")
        precheck_cron_job = (
            f"# {class_name} (precheck)\n"
            f"{precheck_time.minute} {precheck_time.hour} * * {precheck_weekday} "
            f"{program_command} {index} --check "
            f"{output_redirection}"
            "\n"
        )
        return f"{precheck_cron_job}{booking_cron_job}"
    # print(f"[INFO] No precheck")
    return booking_cron_job
