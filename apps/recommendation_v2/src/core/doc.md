# Geolocalisation Pipeline — `playlist_recommendation`

## Overview

This diagram shows how coordinates, IRIS IDs and H3 indexes flow through the
`/playlist_recommendation/{user_id}` route, from coordinate resolution to the
final response.

**Key roles:**
- **`iris_id`** — resolved once at context-build time, written to BigQuery tracking only. Never used for retrieval or ranking.
- **H3 indexes** — used in two independent places: Redis offer-resolution cache key (res-8) and spatial DB pre-filter on `Venue` (variable resolution, ~50 km disk).

```mermaid
flowchart TD
    A["POST /playlist_recommendation/{user_id}"]

    subgraph CoordSource["Coordinate Resolution"]
        GPS{"GPS lat/lng<br/>provided?"}
        GPSSRC["source = gps<br/>use GPS lat/lng"]
        SUB{"Subscription dept<br/>coords in DB?"}
        SUBSRC["source = subscription_department<br/>use dept centroid lat/lng"]
        NOSRC["source = none<br/>lat = None, lng = None"]
        GPS -->|Yes| GPSSRC
        GPS -->|No| SUB
        SUB -->|Yes| SUBSRC
        SUB -->|No| NOSRC
    end

    A --> CoordSource

    subgraph IRISRes["IRIS ID Resolution - geo.py"]
        IRIS1["ST_Contains(shape, point)<br/>on IrisFrance table"]
        IRIS2{"Found?"}
        IRIS3["Fallback: ORDER BY<br/>ST_Distance(centroid, point) LIMIT 1"]
        IRISID["iris_id resolved"]
        IRIS1 --> IRIS2
        IRIS2 -->|Yes| IRISID
        IRIS2 -->|"No - boundary/gap"| IRIS3
        IRIS3 --> IRISID
    end

    GPSSRC --> IRISRes
    SUBSRC --> IRISRes
    NOSRC -->|"iris_id = None"| UC

    subgraph UCBox["UserContext"]
        UC["user_id, lat, lng<br/>iris_id, geolocation_source<br/>age, bookings_count, remaining_credit"]
    end

    IRISID --> UC

    subgraph VertexRet["Retrieval - Vertex AI"]
        VP["payload: user_id + price/date filters<br/>model_type: tops or recommendation<br/>iris_id NOT sent"]
        VR["raw candidate item_ids"]
        VP --> VR
    end

    UC --> VertexRet

    subgraph OfferRes["Offer Resolution - offer_resolution.py + geo.py"]
        H3CACHE["H3 res-8 cell = cache key prefix<br/>Redis MGET - tops items only"]
        CACHEHIT["Cache HIT:<br/>recompute Haversine from<br/>cached venue coords"]
        CACHEMISS["Cache MISS - DB spatial query:<br/>H3 disk(k_rings, 50km)<br/>filter Venue.h3_resN IN cells<br/>Haversine DISTINCT ON item_id"]
        STOREBACK["Redis MSET - store newly<br/>resolved tops offers"]
        H3CACHE -->|hit| CACHEHIT
        H3CACHE -->|miss| CACHEMISS
        CACHEMISS --> STOREBACK
    end

    VR --> OfferRes
    UC -->|"lat/lng for H3 index + distance"| OfferRes

    OfferRes --> RANK["Ranking - Vertex AI reranker"]
    RANK --> DIVER["Diversification - round-robin by category"]

    subgraph TrackBox["Tracking - BigQuery"]
        TRK["iris_id -> past_offer_context table<br/>geolocation_source logged"]
    end

    UC -->|iris_id| TrackBox
    DIVER --> TrackBox
    DIVER --> RESP["RecommendationResponse"]
```
