import ssl
from functools import lru_cache

import certifi


@lru_cache()
def get_ssl_context():
    # TODO: make sure certifi is upgraded frequently
    return ssl.create_default_context(cafile=certifi.where())
