from typing import Annotated

# range is only for documentation (based on PostgreSQL SMALLINT),
# but could in theory be used by a custom type checker
small_integer = Annotated[int, "[-32768,32767]"]
