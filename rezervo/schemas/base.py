from pydantic import BaseModel


class OrmBase(BaseModel):
    class Config:
        orm_mode = True
