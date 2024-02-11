from typing import Optional
from uuid import UUID

import typer
from rich import print as rprint

from rezervo import models
from rezervo.chains.active import get_chain
from rezervo.cli.async_cli import AsyncTyper
from rezervo.database import crud
from rezervo.database.database import SessionLocal
from rezervo.schemas.config.user import ChainIdentifier, ChainUserCredentials
from rezervo.utils.cron_utils import delete_booking_crontab

users_cli = AsyncTyper()


@users_cli.command(name="create")
def create_user(
    name: str,
    jwt_sub: str,
    slack_id: Optional[str] = typer.Option(None),
):
    with SessionLocal() as db:
        db_user = crud.create_user(db, name, jwt_sub, slack_id)
        rprint(f"User '{db_user.name}' created")


@users_cli.command(name="integrate")
def upsert_chain_user(
    name: str,
    chain_identifier: ChainIdentifier,
    username: str,
    password: str,
):
    with SessionLocal() as db:
        user = db.query(models.User).filter_by(name=name).first()  # type: ignore
        if user is None:
            rprint(f"User '{name}' not found")
            raise typer.Exit(1)
        crud.upsert_chain_user_creds(
            db,
            user.id,
            chain_identifier,
            ChainUserCredentials(username=username, password=password),
        )
        rprint(f"User '{user.name}' integrated with {get_chain(chain_identifier).name}")


@users_cli.command(name="delete")
def delete_user(user_id: UUID):
    with SessionLocal() as db:
        delete_booking_crontab(user_id)
        crud.delete_user(db, user_id)


@users_cli.callback(
    invoke_without_command=True,
    context_settings={
        "allow_extra_args": True,
        "ignore_unknown_options": True,
    },
)
def list_users(
    ctx: typer.Context,
    print_uuid: bool = typer.Option(False, "--id", help="Print UUIDs of users"),
):
    if ctx.invoked_subcommand is None:
        with SessionLocal() as db:
            users = db.query(models.User).all()
            for user in users:
                print((f"{user.id} " if print_uuid else "") + str(user.name))
