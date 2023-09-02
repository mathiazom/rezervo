import requests

from rezervo.schemas.config.user import PushNotificationSubscription
from rezervo.settings import get_settings


def send_web_push(subscription: PushNotificationSubscription, message: str) -> None:
    requests.post(
        get_settings().REZERVO_WEB_API + "/notification",
        json={
            "subscription": subscription.dict(),
            "message": message,
            "webPushPrivateKey": get_settings().WEB_PUSH_PRIVATE_KEY,
        },
    )
