from typing import Annotated

from fastapi import Cookie

AuthCookie = Annotated[str | None, Cookie(alias="app.at")]
