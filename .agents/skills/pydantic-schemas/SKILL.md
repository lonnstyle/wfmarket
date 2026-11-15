# Pydantic V2 Data Models for wfmarket

Create and maintain Pydantic V2 response/request models that faithfully reflect the Warframe.Market API data structures, following consistent patterns for validation, naming, and immutability.

## Source of Truth

The API response shapes come from the live Warframe.Market API. When adding new endpoints, the user may provide sample JSON or dict responses — use those as the reference and apply the pattern rules below.

## Model Structure

Every Pydantic model must use V2 syntax:

```python
from __future__ import annotations

from enum import Enum
from typing import Optional
from pydantic import BaseModel, ConfigDict, Field
from datetime import datetime


class Order(BaseModel):
    model_config = ConfigDict(
        populate_by_alias=True,
        extra="ignore",
        frozen=True,
    )
```

### `model_config` rules (always)

| Setting | Value | Why |
|---------|-------|-----|
| `populate_by_alias` | `True` | Allows deserializing from both the alias (JSON key) and the attribute name (Python field) |
| `extra` | `"ignore"` | Drops unknown keys silently — backend may add fields the SDK hasn't modelled yet |
| `frozen` | `True` | Makes models immutable after creation, preventing accidental mutation of response data |

## Field Naming

### JSON key vs Python attribute

The backend uses **snake_case** JSON keys. Map them to **snake_case** Python attributes with `Field(alias="...")`:

```python
# JSON key is "item_id", Python attribute is "item"
item: str = Field(alias="item_id")

# JSON key is "order_type", Python attribute is "order_type" (same — no alias needed)
order_type: OrderType
```

**Rule**: Only use `alias=` when the JSON key differs from the desired Python attribute name. Common cases:
- `item_id` → `item: str` (Go uses `Item` ObjectID, JSON uses `item_id`)
- `creation_date` → `creation_date: datetime` (Go uses `CreatedAt`, JSON uses `creation_date`)
- `last_update` → `last_update: datetime` (Go uses `UpdatedAt`, JSON uses `last_update`)

### Required vs Optional

Derived from Go pointer types and marshmallow `required=False`:

| Go type | Marshmallow | Pydantic | Example |
|---------|-------------|----------|---------|
| `string` (value) | `required=True` | annotated, no default | `order_type: OrderType` |
| `int32` (value) | `required=True` | annotated, no default | `platinum: int` |
| `*int32` | `required=False` | `Optional[int]` with `None` default | `rank: Optional[int] = None` |
| `bool` (value) | `required=False, missing=True` | `bool = True` | `visible: bool = True` |

### Field order

Place fields in this order:
1. Required fields first (no default)
2. Optional fields (with `= None` default)
3. Any computed / non-serializable fields last

## Validation Patterns

### Enum validation

```python
class OrderType(str, Enum):
    sell = "sell"
    buy = "buy"
```

### Range validation

Use `Field()` with `ge`, `gt`, `le`, `lt`:

```python
platinum: int = Field(gt=0, lt=10_000_000)  # 0 < platinum < MAX_PLATINUM
quantity: int = Field(gt=0, lt=10_000)       # 0 < quantity < MAX_QUANTITY
```

Replace `MAX_PLATINUM` and `MAX_QUANTITY` with the actual backend constants:
- `MAX_PLATINUM = 10_000_000`
- `MAX_QUANTITY = 10_000`

### Nested objects

When a field contains a nested object (e.g., `user` in order data), define a separate Pydantic model:

```python
class UserShort(BaseModel):
    id: str
    nickname: str
    platform: Optional[str] = None
```

Then reference it:

```python
class Order(BaseModel):
    # ...
    user: UserShort
```

## Complete Example: Order Model

```python
from __future__ import annotations

from enum import Enum
from typing import Optional
from pydantic import BaseModel, ConfigDict, Field
from datetime import datetime


class OrderType(str, Enum):
    sell = "sell"
    buy = "buy"


class UserShort(BaseModel):
    model_config = ConfigDict(populate_by_alias=True, extra="ignore", frozen=True)

    id: str
    nickname: str
    platform: Optional[str] = None
    crossplay: bool = False
    status: Optional[str] = None


class Order(BaseModel):
    model_config = ConfigDict(populate_by_alias=True, extra="ignore", frozen=True)

    # Required fields
    item_id: str = Field(alias="item_id")
    order_type: OrderType
    platinum: int = Field(gt=0, lt=10_000_000)
    quantity: int = Field(gt=0, lt=10_000)
    visible: bool = True

    # Optional fields (Go pointer types)
    rank: Optional[int] = None
    charges: Optional[int] = None
    amber_stars: Optional[int] = None
    cyan_stars: Optional[int] = None
    subtype: Optional[str] = None

    # Identifiers
    id: str
    per_trade: int = 1

    # Timestamps
    creation_date: Optional[datetime] = None
    last_update: Optional[datetime] = None

    # Nested objects
    user: Optional[UserShort] = None
```

## Request Models (POST / PUT)

Request models mirror the response models but add validation hooks via `@field_validator` and `@model_validator`:

```python
class OrderPostRequest(BaseModel):
    model_config = ConfigDict(populate_by_alias=True, extra="ignore", frozen=True)

    item_id: str
    order_type: OrderType
    platinum: int = Field(gt=0, lt=10_000_000)
    quantity: int = Field(gt=0, lt=10_000)
    visible: bool = True

    rank: Optional[int] = None
    charges: Optional[int] = None
    amber_stars: Optional[int] = None
    cyan_stars: Optional[int] = None
    subtype: Optional[str] = None

    @field_validator("order_type", "subtype", mode="before")
    @classmethod
    def normalize_lower(cls, v: str) -> str:
        """Normalize string fields to lowercase (matches pre_load behavior)."""
        return v.lower() if isinstance(v, str) else v

    @model_validator(mode="after")
    def validate_rank_dependency(self) -> "OrderPostRequest":
        """rank is required only if item has max_rank (validated at API level).
        This model validates locally available constraints."""
        if self.rank is not None and self.rank < 0:
            raise ValueError("rank must be >= 0")
        return self
```

## File Organization

```
src/wfmarket/schemas/
├── v2/
│   ├── __init__.py       # Re-export all v2 models
│   ├── order.py          # Order, OrderType, OrderPostRequest, OrderPutRequest
│   ├── market.py         # Market listing models
│   └── user.py           # User models
├── v1/                   # Legacy v1 models (if any)
│   └── __init__.py
└── ws/                   # WebSocket message models
    └── __init__.py
```

## Checklist When Adding a New Model

- [ ] Uses `ConfigDict(populate_by_alias=True, extra="ignore", frozen=True)`
- [ ] All fields have type hints
- [ ] Optional fields use `Optional[T] = None` (no `| None` on the type alone — must have the default)
- [ ] `alias=` used only when JSON key ≠ Python attribute name
- [ ] Enum types used for fixed-value fields (e.g., `order_type`)
- [ ] Range constraints on numeric fields (`Field(gt=..., lt=...)`)
- [ ] `from __future__ import annotations` at top of file
- [ ] Google-style docstring on the model class
- [ ] Test written and cassette recorded before implementation
- [ ] Model exposed in the appropriate `__init__.py`
