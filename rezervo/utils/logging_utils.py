import logging

from rich.logging import RichHandler

from rezervo.schemas.config.config import read_app_config

logging.basicConfig(
    level=logging.NOTSET if read_app_config().is_development else logging.INFO,
    format="%(message)s",
    datefmt="[%X]",
    handlers=[RichHandler(markup=True, rich_tracebacks=True)],
)
log = logging.getLogger(__name__)
