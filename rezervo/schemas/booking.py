from pydantic import BaseModel


class BookingPayload(BaseModel):
    class_id: str


class BookingCancellationPayload(BaseModel):
    class_id: str
