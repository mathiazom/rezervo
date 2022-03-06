import sys
import datetime
from config import Config
from definitions import APP_ROOT

STARTUP_DAYS_BEFORE_ACTIVITY = 2


def generate_cron_job(index, _class, preparation_minutes):
    # Using current datetime simply as a starting point
    # We really only care about the "wall clock" part, which is replaced by input values
    activity_time = datetime.datetime.now().replace(
        hour=_class.time.hour,
        minute=_class.time.minute,
        second=0, microsecond=0  # Cosmetic only
    )
    print(f"Activity starts on weekday={_class.weekday} at {activity_time.time()}")

    # Back up time to give booking script some prep time
    cron_time = activity_time - datetime.timedelta(minutes=preparation_minutes)

    cron_weekday = (_class.weekday + 1 - STARTUP_DAYS_BEFORE_ACTIVITY) % 7

    print(f"Creating booking cron job at '{cron_time.minute} {cron_time.hour} * * {cron_weekday}'")

    if len(sys.argv) < 1:
        print("[ERROR] No output file path provided")
        return

    return (
        f"{cron_time.minute} {cron_time.hour} * * {cron_weekday} "
        "cd /sit-rezervo/ || exit 1; PATH=$PATH:/usr/local/bin "
        f"/opt/rikardo/bin/python -u rezervo.py {index} >> /var/log/cron.log 2>&1"
        "\n"  # Empty line to please the cron gods ...
    )


def main():
    config = Config.from_config_file(APP_ROOT / "config.yaml")
    cron_spec = ""
    for i, c in enumerate(config.classes):
        cron_spec += generate_cron_job(i, c, config.preperation_minutes)
    with open(sys.argv[1], "w+") as cron_file:
        cron_file.write(cron_spec)


if __name__ == '__main__':
    main()
