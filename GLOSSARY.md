# GLOSSARY

Domain terms and definitions for the wfmarket project, grounded in settled decisions about the Warframe.Market API structure.

## Listings

**Listings** is the umbrella term encompassing both **Orders** and **Auctions**. In most contexts, "listings" refers primarily to Orders. This term is used when querying the combined listings endpoint.

## Orders

**Orders** represent individual buy or sell offers posted by players. Each order has:

- **type**: Either `sell` or `buy`
- **visible**: Boolean flag controlling public visibility. The order owner and moderators can always view the order regardless of this flag; `visible` only affects other users.

## Auctions

**Auctions** (codename throughout the project) represent player auctions for bidding. The site (warframe.market) renamed some endpoints to "Contracts" for direct sell, but the codebase consistently uses `auctions` for the bidding feature. "Contracts" is a site alias, not a game term. Auctions can contain **Riven** items as one of their auctioned goods.

## Riven

**Riven** is a distinct entity that can appear as an item within an **Auction**. Rivens have randomized mods with varying tiers.

## Veiled Riven

A **Veiled Riven** is a riven that has not yet been revealed — the player must complete a challenge to determine which weapon and mods it contains. In the API, veiled rivens are treated as a generic **Item**, not as a Riven entity.

## Item

**Item** represents a generic Warframe game item (weapons, warframes, resources, etc.). Used for veiled rivens and other non-riven items in the API.

## Faction

A **Faction** is a group of NPCs in the game. Factions are runtime-fetched — they can change when the game adds new factions through updates — and are cached locally to avoid redundant API calls.

## Manifest

A **Manifest** is a read-only dataset endpoint that provides reference data about the game. Manifests are cached locally and invalidated by comparing version hashes from the **Versions** endpoint.

### Manifest Types

| Manifest | Endpoint |
|----------|----------|
| Items | `/v2/items` |
| Rivens — Weapons | `/v2/riven/weapons` |
| Rivens — Attributes | `/v2/riven/attributes` |
| Liches | `/v2/liches` |
| Sisters | `/v2/sisters` |
| Missions | `/v2/missions` |
| NPCs | `/v2/npcs` |
| Locations | `/v2/locations` |

Some manifests have sub-manifests (e.g., `/v2/riven/weapons`, `/v2/riven/attributes`).

## Versions

The **Versions** endpoint (`/v2/versions`) provides versioning information for cache invalidation:

- **apiVersion**: String identifying the API package version — used to check if the client package is outdated.
- **collections**: A dictionary mapping manifest names to their version hashes (e.g., `locations`, `items`, `missions`). Comparing these hashes against cached data determines whether the cache should be invalidated.

## Stats

**Stats** are per-item sub-endpoints that provide historical price and volume data:

- **Daily stats**: Last 90 days
- **Hourly stats**: Last 48 hours

Each data point includes: number of closed orders, average price, volume, weighted moving average (WMA), minimum price, and maximum price.

## User Endpoints

| Endpoint | Description |
|----------|-------------|
| `/v2/me` | Authenticated self — returns data for the currently logged-in user |
| `/v2/user/{slug}` | Public — retrieves data for a user identified by their slug |

## Authentication

- **JWT**: Current authentication method. Users authenticate with a JSON Web Token.
- **OAuth 2.0**: Planned but not yet implemented — tracked as a TODO feature.

## WebSocket

The **WebSocket** interface provides real-time streaming of API events. Messages use a **discriminated union** pattern: all messages share a common base model with a `type` field that determines which event variant to deserialize into.

## Pagination

The Warframe.Market API does not paginate responses. All results are returned as raw lists.

## Platform

**Platform** is a filter parameter available for Listings/Auctions queries. It is an enum with values: `pc`, `ps4`, `xbox`, `switch`, `mobile`. Platform data is stable and rarely changes, so it uses an enum. Other query filters that reference shared data (e.g., item names) use plain strings.

## Cache

**Cache** refers to local file-based storage (in `.wfmarket_cache/`) of manifest data. Cache invalidation is driven by comparing collection hashes from the **Versions** endpoint against stored hashes, and optionally by checking the `updatedAt` timestamp (ISO format string).
