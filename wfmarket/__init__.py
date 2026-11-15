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

del NamedTuple, VersionInfo