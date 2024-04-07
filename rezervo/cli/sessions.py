from typing import Optional

import typer

from rezervo import models
from rezervo.chains.active import ACTIVE_CHAIN_IDENTIFIERS
from rezervo.cli.async_cli import AsyncTyper
from rezervo.database.database import SessionLocal
from rezervo.schemas.config.user import ChainIdentifier
from rezervo.sessions import pull_sessions
from rezervo.utils.logging_utils import log

sessions_cli = AsyncTyper()


@sessions_cli.command(name="pull")
async def pull_sessions_cli(
    name: Optional[str] = typer.Option(None, help="Name of user to pull sessions for"),
    chain_identifier: Optional[ChainIdentifier] = typer.Option(
        None, "--chain", help="Identifier of chain to pull sessions from"
    ),
):
    if (
        chain_identifier is not None
        and chain_identifier not in ACTIVE_CHAIN_IDENTIFIERS
    ):
        log.error(f"Chain '{chain_identifier}' not found")
        raise typer.Exit(1)
    user = None
    if name is not None:
        with SessionLocal() as db:
            user = db.query(models.User).filter_by(name=name).first()
            if user is None:
                log.error(f"User '{name}' not found")
                raise typer.Exit(1)
    await pull_sessions(chain_identifier, user.id if user is not None else None)
