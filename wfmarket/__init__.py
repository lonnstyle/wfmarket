__title__ = "wfmarket"
__author__ = "lonnstyle"
__license__ = "MIT"
__copyright__ = "Copyright 2026-present lonnstyle"
__version__ = "0.1.0"

from typing import NamedTuple


class VersionInfo(NamedTuple):
    major: int
    minor: int
    micro: int
    releaselevel: str
    serial: int


version_info = VersionInfo(major=0, minor=1, micro=0, releaselevel="alpha", serial=0)

# Public API
__all__ = [
    "LANGUAGES",
    "Client",
    "Language",
    "Platform",
]

from wfmarket import constants as _c
from wfmarket.client import Client

# Convenience re-exports (static analysis tools respect __all__).
Language = _c.Language
LANGUAGES = _c.LANGUAGES
Platform = _c.Platform

# Singleton instance — replace with a new Client() for custom headers.
client: Client = Client()

del NamedTuple, VersionInfo
