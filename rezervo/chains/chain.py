from abc import abstractmethod

from rezervo.chains.schema import ChainProfileImages
from rezervo.providers.provider import Provider
from rezervo.schemas.config.user import ChainIdentifier


class Chain(Provider):
    @property
    @abstractmethod
    def identifier(self) -> ChainIdentifier:
        raise NotImplementedError()

    @property
    @abstractmethod
    def name(self) -> str:
        raise NotImplementedError()

    @property
    @abstractmethod
    def images(self) -> ChainProfileImages:
        raise NotImplementedError()
