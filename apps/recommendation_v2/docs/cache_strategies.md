# Cache Strategies — Recommendation API V2

This document describes the two caching strategies used in the Recommendation API V2.
Both rely on the same Redis infrastructure and share the same expiry logic.

---

## Table of Contents

1. [Shared Infrastructure](#-1-shared-infrastructure)
2. [Strategy 1 — Endpoint Response Cache](#-2-strategy-1--endpoint-response-cache)
3. [Strategy 2 — Offer Resolution Cache](#-3-strategy-2--offer-resolution-cache)
4. [TTL & Refresh Cycle](#-4-ttl--refresh-cycle)
5. [Feature Flags & Environment Variables](#️-5-feature-flags--environment-variables)
6. [Error Handling & Failsafe Behavior](#-6-error-handling--failsafe-behavior)

---

## 🔧 1. Shared Infrastructure

### `src/services/redis.py` — `RedisCacheService`

Low-level layer managing the Redis connection lifecycle and JSON serialization/deserialization.

| Method | Role |
|---|---|
| `connect()` | Opens the connection at app startup (FastAPI lifespan). Silently disables the cache on failure. |
| `disconnect()` | Gracefully closes the connection at app shutdown. |
| `get_cached_value(key)` | Single read (`GET`). Returns `None` if absent or on error. |
| `set_cached_value(key, value, ttl)` | Single write (`SET … EX`). |
| `mget_cached_values(keys)` | Batch read (`MGET`) — single network round-trip. |
| `mset_cached_values(kv_pairs, ttl)` | Batch write via Redis pipeline (`SET … EX` × N) — single network round-trip. |

A **background monitoring task** runs continuously and periodically logs the number of active connections to the Redis instance. A distributed Redis lock (`SET NX`) ensures that only one worker logs at a time, preventing log flooding in multi-worker / multi-instance deployments.

### `src/connectors/redis_api.py` — `RedisAPI`

Mid-level connector implementing both caching strategies on top of `RedisCacheService`.

Shared utilities:

- **`generate_cache_key(namespace, signature_data)`**: serializes the signature dict to sorted JSON, generates an MD5 hash, and returns a key of the form `{namespace}:{md5}`.
- **`calculate_seconds_until_next_database_population_time()`**: computes the TTL (in seconds) until the next configured reset hour (`REDIS_CACHE_RESET_HOUR`). Used by both strategies to align cache expiry with the nightly database reload (see [TTL & Refresh Cycle](#-4-ttl--refresh-cycle)).

---

## ⚡ 2. Strategy 1 — Endpoint Response Cache

### Goal

Return the full pipeline result instantly for an identical repeated HTTP request, without calling Vertex AI models or querying the database.

### Covered endpoints

- `POST /playlist_recommendation/{user_id}` — `src/api/playlist_recommendation.py`
- `GET /similar_offers/{offer_id}` — `src/api/similar_offer.py`

### How it works

```
Incoming request
      │
      ▼
Build request signature (dict → MD5 hash)
      │
      ├──[CACHE HIT]──► Cached response returned immediately
      │                 • from_cache = True
      │                 • unique_call_id regenerated (new UUID)
      │                 • original call_id preserved
      │
      └──[CACHE MISS]──► Full pipeline executed
                         └──► Result stored in cache (TTL = next nightly reset)
```

### Cache key composition

The signature dict is built from:

| Field | playlist_recommendation | similar_offer |
|---|---|---|
| Identifier | `user_id` | `offer_id` + `user_id` |
| Location | `location_h3` (H3 resolution `ENDPOINT_RESPONSE_CACHE_H3_RESOLUTION`, default: 8) | `location_h3` (same) |
| Filters | `params` (full JSON body) | `categories`, `subcategories`, `search_group_names` |
| Model | — | `retrieval_model` |

> **Why H3 instead of raw GPS coordinates?**
> GPS coordinates vary slightly between requests due to signal precision. By normalizing them into an H3 cell (resolution 8 ≈ 0.74 km²), two requests made from the same neighborhood share the same cache signature, significantly increasing the hit rate.

### `call_id` management

- On a **cache hit**, a new `unique_call_id` is injected into the response.
- The original `call_id` (generated during the initial pipeline run) is **intentionally preserved**.
- This allows click/booking events from the mobile client to reference the correct pipeline call in BigQuery, even when the response was served from cache.

### Control flag

Enabled via `ENDPOINT_RESPONSE_CACHE_ENABLED` (itself gated by `REDIS_CACHE_ENABLED`).

---

## 📍 3. Strategy 2 — Offer Resolution Cache

### Context

Spatial resolution (step 3 of the pipeline) transforms abstract ML items (e.g. "The Matrix film") into concrete physical offers (e.g. "Screening at 8 PM, cinema 2 km away"). For **multi-venue items** (the same film screened in multiple cinemas), the API runs a SQL query to select only the closest venue for each item.

The distance is computed using the **Haversine formula expressed as standard SQL math functions** (`sin`, `cos`, `acos`, `radians`) — not PostGIS-specific functions like `ST_Distance`. This keeps the distance calculation database-agnostic and makes it easier to switch to a different database engine if needed.

This SQL query can become expensive when many users in the same geographic area request the same popular items.

### Goal

Cache the result of the spatial resolution (`offer_id`, venue coordinates) for **"tops"** items (the most stable and popular items), keyed by H3 geographic zone, to avoid repeating the SQL query for every user located in the same zone.

### Which items are cached?

Only items with `item_origin == ItemOrigin.TOPS` are eligible for caching.

> **Why only "tops" items?**
> "Tops" items are the most popular and most redundant offers across Vertex AI calls. They appear frequently in the playlists of many geographically close users, which maximizes the cache hit rate. Personalized items (non-tops) vary too much across users to be worth caching.

### How it works

```
Incoming multi-venue items
          │
          ├── Non-tops ──────────────────────────────────► SQL query (always)
          │
          └── Tops
                │
                ▼
        Redis MGET (single round-trip)
                │
                ├──[HIT]──► Distance recomputed in pure Python (Haversine)
                │            • No SQL call
                │            • Guard: item skipped if now outside search radius
                │
                └──[MISS]──► SQL query batched with non-tops items
                              └──► Results stored in cache (Redis pipeline MSET)
                                   • Only resolved items are cached
                                   • Items with no venue found are NOT cached
```

### Cache key format

```
offer_resolution:r{resolution}:{h3_cell}:{item_id}
```

Example: `offer_resolution:r8:8928308280fffff:item-42`

- `r{resolution}`: H3 resolution used (configurable via `OFFER_RESOLUTION_CACHE_H3_RESOLUTION`, default: 8)
- `{h3_cell}`: H3 cell computed from the user's coordinates
- `{item_id}`: item identifier

> The resolution is embedded in the key to prevent collisions if the configuration changes and to make the key self-describing.

### Cached payload (per item)

Only the fields that cannot be derived from Vertex AI item data are stored:

| Field | Description |
|---|---|
| `offer_id` | Identifier of the closest offer in this geographic zone |
| `venue_latitude` | Venue latitude |
| `venue_longitude` | Venue longitude |
| `offer_creation_date` | Offer creation date (ISO 8601 string) |
| `stock_beginning_date` | Stock start date (ISO 8601 string) |

### Partial hits

Redis lookups are performed in batch via **MGET**: some items can be cache hits while others are misses within the same request. Only missing items are sent to the database.

### Guard — search radius boundary

After a cache hit, the exact distance is recomputed via the pure Python `calculate_haversine_distance_in_meters` function. If a venue now falls outside the search radius (an edge case at H3 cell boundaries), the item is silently skipped rather than returned as an invalid result.

### Control flag

Enabled via `OFFER_RESOLUTION_CACHE_ENABLED` (itself gated by `REDIS_CACHE_ENABLED`).

---

## 🕐 4. TTL & Refresh Cycle

Both strategies use the **same dynamic TTL**: the time remaining until the next configured reset hour (`REDIS_CACHE_RESET_HOUR`, default: `5` for 5:00 AM UTC).

**Business rule:** the database is re-imported every night around 3–4 AM with fresh data — new offers created the previous day, new users, updated stock, etc. The cache reset hour is set to 5 AM to give the nightly import enough time to complete, ensuring users always receive up-to-date recommendations after the reload.

```python
# Example: if the current time is 2:30 PM and REDIS_CACHE_RESET_HOUR = 5
# TTL = time until tomorrow at 05:00 AM = ~14.5 hours
ttl = RedisAPI.calculate_seconds_until_next_database_population_time()
```

---

## ⚙️ 5. Feature Flags & Environment Variables

| Variable | Role | Local default | Prod default |
|---|---|---|---|
| `REDIS_CACHE_ENABLED` | **Master switch** — disables all Redis caching when `0` | `0` | `1` |
| `REDIS_URL` | Redis connection string (e.g. `redis://localhost:6379/0`) | `redis://localhost:6379/0` | — |
| `REDIS_CACHE_RESET_HOUR` | Hour [0-23] of daily cache expiry | `5` | `5` |
| `REDIS_AUTH_STRING` | Redis authentication token (optional) | `""` | — |
| `REDIS_CA_CERT_PATH` | Path to PEM certificate for Redis TLS | `""` | — |
| `ENDPOINT_RESPONSE_CACHE_ENABLED` | Enables the HTTP endpoint response cache | `0` | `1` |
| `ENDPOINT_RESPONSE_CACHE_H3_RESOLUTION` | H3 resolution for the location signature | `8` | `8` |
| `OFFER_RESOLUTION_CACHE_ENABLED` | Enables the offer resolution cache | `0` | `1` |
| `OFFER_RESOLUTION_CACHE_H3_RESOLUTION` | H3 resolution for offer resolution cache keys | `8` | `8` |

> `ENDPOINT_RESPONSE_CACHE_ENABLED` and `OFFER_RESOLUTION_CACHE_ENABLED` are automatically forced to `False` when `REDIS_CACHE_ENABLED=0`, even if their individual environment variables are set to `1`. A single flag is enough to fully disable Redis.

---

## 🛡️ 6. Error Handling & Failsafe Behavior

The cache is designed to be **non-blocking**: any Redis error (lost connection, timeout, serialization failure) is silently caught and logged at `WARNING` level. The API continues to operate normally without cache, as if `REDIS_CACHE_ENABLED=0`.

This failsafe behavior also applies at startup: if Redis is unreachable when the app starts, `REDIS_CACHE_ENABLED` is automatically set to `False` and no reconnection is attempted for the lifetime of the process.
