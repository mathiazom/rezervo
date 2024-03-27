from uuid import UUID

from rezervo.cli.async_cli import AsyncTyper
from rezervo.providers.ibooking.auth_session import (
    extend_auth_session_silently,
    initialize_auth_session_interactively,
    sustain_auth_session_silently,
)

x_cli = AsyncTyper()


@x_cli.command()
async def init() -> None:
    initialize_auth_session_interactively(
        "sit", UUID("50aa9cb8-9e16-4138-bbb0-d820b3df9f04")
    )


@x_cli.command()
async def extend() -> None:
    extend_auth_session_silently("sit", UUID("50aa9cb8-9e16-4138-bbb0-d820b3df9f04"))


@x_cli.command()
async def sustain() -> None:
    sustain_auth_session_silently("sit", UUID("50aa9cb8-9e16-4138-bbb0-d820b3df9f04"))
