"""Async API client for Warframe.Market."""

from __future__ import annotations

import json
import types
from typing import Any

import httpx
from typing_extensions import Self

import wfmarket.constants as _c
from wfmarket._rate_limiter import rate_limiter

# Package version for User-Agent fallback — imported lazily to avoid circular
# imports (wfmarket/__init__.py imports Client from this module).
_VERSION: str | None = None


def _get_version() -> str:
    """Return the package version, importing lazily to break the cycle."""
    global _VERSION
    if _VERSION is None:
        import wfmarket as _pkg

        _VERSION = _pkg.__version__
    return _VERSION


class Client:
    """Async HTTP client for Warframe.Market.

    Manages an underlying :class:`httpx.AsyncClient` and attaches global
    request headers to every outgoing API call.

    Singleton Pattern
    -----------------
    Never instantiate :class:`Client` directly. Use the module-level
    ``wfmarket.client`` singleton — replace it with a new instance if you need
    custom header values::

        import wfmarket

        # Default headers
        async with wfmarket.client:
            ...

        # Custom headers
        wfmarket.client = wfmarket.Client(
            platform=wfmarket.Platform.XBOX,
            language="ja",
            crossplay=True,
        )

    Args:
        user_agent: Custom User-Agent header value. Falls back to
            ``wfmarket.py/{__version__}`` when omitted or ``None``.
        language: Preferred response language (lowercase locale code).
            Defaults to ``en``.
        platform: Target platform for marketplace data. Defaults to
            :attr:`Platform.PC`.
        crossplay: Whether to include crossplay-compatible orders.
            Defaults to ``False``.

    Raises:
        ValueError: If *language* is not a supported code, if *platform* is
            invalid, or if *platform* is :attr:`Platform.SWITCH` and
            *crossplay* is ``True`` (Switch does not support crossplay).
    """

    __slots__ = ("_base_url", "_headers", "_http_client")

    _API_BASE: str = "https://api.warframe.market"

    def __init__(
        self,
        user_agent: str | None = None,
        language: _c.Language | str | None = None,
        platform: _c.Platform | None = None,
        crossplay: bool = False,
    ) -> None:
        # --- Validate inputs ------------------------------------------------
        if language is None:
            lang = _c.LANGUAGE_DEFAULT
        else:
            try:
                lang = _c.Language(language)
            except ValueError:
                raise ValueError(f"Unsupported language {language!r}. Must be one of: {[l.value for l in _c.LANGUAGES]}")

        plat = platform if platform is not None else _c.PLATFORM_DEFAULT

        if plat not in _c.SUPPORTED_PLATFORMS:
            raise ValueError(
                f"Unsupported platform {platform!r}. Must be one of: {[p.value for p in _c.SUPPORTED_PLATFORMS]}"
            )

        if crossplay and plat == _c.Platform.SWITCH:
            raise ValueError("Switch does not support crossplay. Cannot set platform=switch with crossplay=True.")

        # --- Build headers --------------------------------------------------
        ua = user_agent if user_agent is not None else f"wfmarket.py/{_get_version()}"

        self._headers: dict[str, str] = {
            "User-Agent": ua,
            "Language": lang,
            "Platform": plat.value,
            "Crossplay": ("false", "true")[crossplay],
            "Accept": "application/json",
        }

        # --- httpx transport ------------------------------------------------
        self._http_client = httpx.AsyncClient(
            base_url=self._API_BASE,
            headers=self._headers,
            timeout=httpx.Timeout(30.0),
        )

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    async def __aenter__(self) -> Self:
        """Enter the async context manager; open the httpx client."""
        await self._http_client.__aenter__()
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None = None,
        exc_value: BaseException | None = None,
        traceback: types.TracebackType | None = None,
    ) -> None:
        """Exit the async context manager; close the httpx client."""
        await self._http_client.__aexit__(exc_type, exc_value, traceback)

    async def close(self) -> None:
        """Close the underlying httpx client."""
        await self._http_client.aclose()

    # ------------------------------------------------------------------
    # Properties
    # ------------------------------------------------------------------

    @property
    def base_url(self) -> str:
        """The API base URL (e.g. ``https://api.warframe.market``)."""
        return self._API_BASE

    @property
    def headers(self) -> dict[str, str]:
        """Read-only view of the global request headers."""
        return dict(self._headers)

    @property
    def user_agent(self) -> str:
        """Current User-Agent header value."""
        return self._headers["User-Agent"]

    @property
    def language(self) -> str:
        """Current Language header value."""
        return self._headers["Language"]

    @property
    def platform(self) -> _c.Platform:
        """Current Platform header value."""
        return _c.Platform(self._headers["Platform"])

    @property
    def crossplay(self) -> bool:
        """Current Crossplay header value (deserialized)."""
        return json.loads(self._headers["Crossplay"])

    # ------------------------------------------------------------------
    # Request dispatch
    # ------------------------------------------------------------------

    async def _request(
        self,
        method: str,
        path: str,
        **kwargs: Any,
    ) -> httpx.Response:
        """Execute an HTTP request with rate limiting.

        Args:
            method: HTTP method (GET, POST, etc.).
            path: URL path relative to :attr:`base_url`.
            **kwargs: Extra keyword arguments forwarded to
                :meth:`httpx.AsyncClient.request`.

        Returns:
            The httpx response.

        Raises:
            WfMarketRateLimitError: If rate limiting blocks the request.
        """
        url = f"/{path.lstrip('/')}"

        # Acquire tokens from the rate limiter before sending.
        await rate_limiter.acquire(url)

        return await self._http_client.request(method, url, **kwargs)

    async def get(self, path: str, **kwargs: Any) -> httpx.Response:
        """Send a GET request.

        Args:
            path: URL path relative to :attr:`base_url`.
            **kwargs: Extra keyword arguments forwarded to
                :meth:`httpx.AsyncClient.get`.

        Returns:
            The httpx response.
        """
        return await self._request("GET", path, **kwargs)

    async def post(self, path: str, **kwargs: Any) -> httpx.Response:
        """Send a POST request.

        Args:
            path: URL path relative to :attr:`base_url`.
            **kwargs: Extra keyword arguments forwarded to
                :meth:`httpx.AsyncClient.post`.

        Returns:
            The httpx response.
        """
        return await self._request("POST", path, **kwargs)
