from rezervo.cli.async_cli import AsyncTyper
from rezervo.cli.fusionauth.init import init

fusionauth_cli = AsyncTyper()
fusionauth_cli.command()(init)
