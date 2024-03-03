from humps import camelize
from pydantic import BaseModel


class CamelModel(BaseModel):
    class Config:
        alias_generator = camelize
        allow_population_by_field_name = True


# TODO: needs improvement, this is mostly to please MyPy
class CamelOrmBase(CamelModel):
    class Config:
        orm_mode = True
