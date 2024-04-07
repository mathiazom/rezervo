import logging

from rich.logging import RichHandler

from rezervo.settings import get_settings

logging.basicConfig(
    level=logging.NOTSET if get_settings().IS_DEVELOPMENT else logging.INFO,
    format="%(message)s",
    datefmt="[%X]",
    handlers=[RichHandler(markup=True, rich_tracebacks=True)],
)
log = logging.getLogger(__name__)
