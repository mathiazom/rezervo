from rezervo.cli.async_cli import AsyncTyper
from rezervo.cli.fusionauth.init import init
from rezervo.cli.fusionauth.migrate import migrate_from_auth0

fusionauth_cli = AsyncTyper()
fusionauth_cli.command()(init)
fusionauth_cli.command(name="migrate")(migrate_from_auth0)
