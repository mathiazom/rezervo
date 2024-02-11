from aiohttp import ClientSession, DummyCookieJar, TCPConnector
from rich import print as rprint

from rezervo.utils.ssl_utils import get_ssl_context


def create_tcp_connector() -> TCPConnector:
    return TCPConnector(ssl_context=get_ssl_context())


def create_client_session():
    return ClientSession(
        connector=create_tcp_connector(),
    )


class HttpClient:
    _session = None

    @classmethod
    def singleton(cls) -> ClientSession:
        if cls._session is None:
            rprint("✨  Creating shared ClientSession")
            cls._session = ClientSession(
                connector=create_tcp_connector(),
                cookie_jar=DummyCookieJar(),  # ignore collected cookies
            )
        return cls._session

    @classmethod
    async def close_singleton(cls) -> None:
        if cls._session is not None:
            rprint("🛑  Closing shared ClientSession")
            await cls._session.close()
            cls._session = None
