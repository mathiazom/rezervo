import apprise

from rezervo.schemas.config.config import read_app_config

aprs = apprise.Apprise()
app_config = read_app_config()
if (notifications := app_config.notifications) is not None and (
    apprise_config := notifications.apprise
) is not None:
    config = apprise.AppriseConfig()
    config.add(apprise_config.config_file)
    aprs.add(config)
