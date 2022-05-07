from __future__ import annotations

from os import PathLike
from typing import Optional

import typing
from munch import Munch
import yaml


class Config(Munch):
    """Glorified Munch object for handling harvesting configurations"""

    @classmethod
    def from_config_file(cls, path: str | bytes | PathLike[str] | PathLike[bytes] | int) -> Optional[Config]:
        """Create config object from YAML config file"""
        with open(path) as file:
            try:
                config = yaml.safe_load(file)
                return typing.cast(Config, cls.fromDict(config))
            except yaml.YAMLError as exc:
                print(f"[FAIL] Error while loading YAML config: {exc}")
        return None
