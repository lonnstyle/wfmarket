"""Custom exception hierarchy for wfmarket."""

from __future__ import annotations


class WfMarketError(Exception):
    """Base exception for all wfmarket errors."""

    def __str__(self) -> str:
        return super().__str__() or self.__class__.__name__

    def __repr__(self) -> str:
        args = super().__str__()
        if args:
            return f"{self.__class__.__name__}({args!r})"
        return self.__class__.__name__


class WfMarketHTTPError(WfMarketError):
    """HTTP-level failures (timeout, connection, etc.)."""


class WfMarketAPIError(WfMarketError):
    """Non-2xx API responses."""


class WfMarketValidationError(WfMarketError):
    """Pydantic validation failures."""


class WfMarketRateLimitError(WfMarketError):
    """Rate limit exceeded."""


class WfMarketCacheError(WfMarketError):
    """Cache read/write failures."""
