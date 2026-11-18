"""Constants for Warframe.Market API request headers."""

from __future__ import annotations

from enum import Enum

# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

__all__ = [
    # Language — user-facing type and collection.
    "LANGUAGES",
    "LANGUAGE_DEFAULT",
    "Language",
    # Platform — user-facing enum.
    "Platform",
]

# ---------------------------------------------------------------------------
# Language
# ---------------------------------------------------------------------------


class Language(str, Enum):
    """Supported languages for Warframe.Market API responses.

    Inherits from ``str`` so enum members compare equal to their code:
    ``Language.KO == "ko"`` is ``True``.
    """

    EN = "en"
    KO = "ko"
    RU = "ru"
    DE = "de"
    FR = "fr"
    PT = "pt"
    ZH_HANS = "zh-hans"
    ZH_HANT = "zh-hant"
    ES = "es"
    IT = "it"
    PL = "pl"
    UK = "uk"
    TR = "tr"
    JA = "ja"


LANGUAGES: tuple[Language, ...] = (
    Language.EN,
    Language.KO,
    Language.RU,
    Language.DE,
    Language.FR,
    Language.PT,
    Language.ZH_HANS,
    Language.ZH_HANT,
    Language.ES,
    Language.IT,
    Language.PL,
    Language.UK,
    Language.TR,
    Language.JA,
)

LANGUAGE_DEFAULT: Language = Language.EN


# ---------------------------------------------------------------------------
# Platform
# ---------------------------------------------------------------------------


class Platform(str, Enum):
    """Supported platforms for Warframe.Market marketplace data.

    Switch does not support crossplay — attempting to combine
    ``Platform.SWITCH`` with ``crossplay=True`` raises a ``ValueError``.
    """

    PC = "pc"
    PS4 = "ps4"
    XBOX = "xbox"
    SWITCH = "switch"
    MOBILE = "mobile"


# ---------------------------------------------------------------------------
# Internal helpers (not in __all__ — hidden from static analysis)
# ---------------------------------------------------------------------------

PLATFORM_DEFAULT: Platform = Platform.PC
SUPPORTED_PLATFORMS: frozenset[Platform] = frozenset({p for p in Platform})

# Platforms that support crossplay.
CROSSPLAY_CAPABLE_PLATFORMS: frozenset[Platform] = frozenset(
    {
        Platform.PC,
        Platform.PS4,
        Platform.XBOX,
        Platform.MOBILE,
    }
)
