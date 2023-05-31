from pydantic import BaseModel


class BookingPayload(BaseModel):
    class_id: str
