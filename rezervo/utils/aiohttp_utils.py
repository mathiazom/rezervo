from aiohttp import TCPConnector

from rezervo.utils.ssl_utils import get_ssl_context

# TODO: use a global-ish ClientSession instead of creating a new one for each request


def create_tcp_connector() -> TCPConnector:
    return TCPConnector(ssl_context=get_ssl_context())
