from pydantic import BaseModel


class Features(BaseModel):
    class_reminder_notifications: bool
