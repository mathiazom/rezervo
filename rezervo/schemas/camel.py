from humps import camelize
from pydantic import BaseModel, ConfigDict


class CamelModel(BaseModel):
    model_config = ConfigDict(alias_generator=camelize, populate_by_name=True)


# TODO: needs improvement, this is mostly to please MyPy
class CamelOrmBase(CamelModel):
    model_config = ConfigDict(from_attributes=True)
