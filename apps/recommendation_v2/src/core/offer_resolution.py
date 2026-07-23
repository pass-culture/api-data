from datetime import datetime

from sqlalchemy.ext.asyncio import AsyncSession

from config import settings
from connectors.redis_api import RedisAPI
from connectors.redis_api import redis_api
from core.geo import MAX_DISTANCE_METERS_FOR_OFFER_RETRIEVAL
from core.geo import calculate_haversine_distance_in_meters
from core.geo import find_closest_offers_with_h3_index
from core.user_context import UserContext
from schemas.enriched_offer import EnrichedRecommendableOffer
from schemas.vertex_prediction_item import ItemOrigin
from schemas.vertex_prediction_item import RecommendableItem
from services.h3 import get_h3_index_from_coordinates
from services.logger import logger


DEFAULT_MAX_DISTANCE_IN_METERS = 100_000


async def _fetch_tops_offer_resolutions_from_cache(
    tops_item_ids: list[str],
    user_context: UserContext,
) -> tuple[dict[str, dict], list[str], str]:
    """
    Looks up pre-resolved tops offers from the Redis offer-resolution cache (single MGET round-trip).

    Args:
        tops_item_ids: IDs of "tops" items to look up in the cache. Must be non-empty.
        user_context: Standardized user context — must be geolocated when calling this function.

    Returns:
        A 3-tuple of:
        - cache_hits (dict[str, dict]): item_id → cached offer payload for items found in cache.
        - tops_cache_misses (list[str]): item IDs not found in cache, to be resolved via SQL.
        - h3_cell (str): The H3 cell used for cache key construction.
    """

    h3_cell = get_h3_index_from_coordinates(
        user_context.latitude,
        user_context.longitude,
        resolution=settings.OFFER_RESOLUTION_CACHE_H3_RESOLUTION,
    )
    assert h3_cell is not None, "h3_cell must not be None when user is geolocated"  # help ty
    cache_keys = [
        redis_api.build_offer_resolution_cache_key(h3_cell, iid, settings.OFFER_RESOLUTION_CACHE_H3_RESOLUTION)
        for iid in tops_item_ids
    ]
    cached_values = await redis_api.mget_resolved_offers(cache_keys)

    cache_hits = {
        item_id: cached_value
        for item_id, cached_value in zip(tops_item_ids, cached_values, strict=True)
        if cached_value is not None
    }
    cache_hit_ids: set[str] = set(cache_hits)
    tops_cache_misses = [iid for iid in tops_item_ids if iid not in cache_hit_ids]

    return cache_hits, tops_cache_misses, h3_cell


async def _store_tops_offer_resolutions_in_cache(
    tops_cache_misses: list[str],
    db_rows: list,
    h3_cell: str,
) -> None:
    """
    Stores newly DB-resolved tops offer resolutions in the Redis cache (single MSET pipeline).

    Only items that were actually resolved (i.e. had at least one venue within the search radius)
    are written to cache. Unresolved items (no venue found) are intentionally not cached.

    Args:
        tops_cache_misses: Item IDs that were not found in cache and were resolved via SQL.
        db_rows: Raw results from the spatial DB query, as (db_offer, distance) tuples.
        h3_cell: The H3 cell identifier used as part of each cache key.
    """
    db_resolved_by_item_id = {db_offer.item_id: db_offer for db_offer, _ in db_rows}
    new_cache_entries: dict[str, dict] = {
        redis_api.build_offer_resolution_cache_key(h3_cell, item_id, settings.OFFER_RESOLUTION_CACHE_H3_RESOLUTION): {
            "offer_id": db_offer.offer_id,
            "venue_latitude": float(db_offer.venue_latitude) if db_offer.venue_latitude is not None else None,
            "venue_longitude": float(db_offer.venue_longitude) if db_offer.venue_longitude is not None else None,
            # Serialize as ISO 8601 strings for JSON-safe Redis storage
            "offer_creation_date": db_offer.offer_creation_date.isoformat() if db_offer.offer_creation_date else None,
            "stock_beginning_date": db_offer.stock_beginning_date.isoformat()
            if db_offer.stock_beginning_date
            else None,
        }
        for item_id in tops_cache_misses
        # Item was not resolved (e.g. no venue within radius) — do not cache absence.
        if (db_offer := db_resolved_by_item_id.get(item_id)) is not None
    }

    if new_cache_entries:
        ttl = RedisAPI.calculate_seconds_until_next_database_population_time()
        await redis_api.mset_resolved_offers(new_cache_entries, ttl)
        logger.debug(
            "💾 Newly resolved tops offers stored in cache.",
            extra={
                "stored_count": len(new_cache_entries),
                "not_resolved_count": len(tops_cache_misses) - len(new_cache_entries),
                "ttl_seconds": ttl,
                "h3_cell": h3_cell,
            },
        )


async def _resolve_multi_venue_items(
    db: AsyncSession,
    multi_venue_item_ids: list[str],
    item_lookup_map: dict[str, RecommendableItem],
    user_context: UserContext,
) -> list[EnrichedRecommendableOffer]:
    """
    Resolves multi-venue physical items into their closest offers.

    When the offer-resolution cache is enabled, "tops" items already resolved in the same H3 zone
    are served from Redis, skipping the spatial SQL query entirely for those items.

    Strategy:
    - "tops" items (most redundant in Vertex retrieval results) are checked in Redis first (MGET)
      when the cache is enabled. Cache hits skip the SQL query entirely; their distance is
      recomputed via pure-Python Haversine.
    - Cache misses, non-tops items, and all items when cache is disabled are resolved via a
      single batched spatial SQL query.
    - Newly DB-resolved tops items are written back to Redis in a single pipeline (MSET).

    Cached payload per item (minimal — only what cannot be derived from Vertex AI item data):
        offer_id, venue_latitude, venue_longitude, offer_creation_date, stock_beginning_date

    Args:
        db: The async database session.
        multi_venue_item_ids: IDs of items requiring SQL spatial resolution.
        item_lookup_map: Mapping of item_id → RecommendableItem (Vertex AI data).
        user_context: Standardized user context — must be geolocated when calling this function.

    Returns:
        list[EnrichedRecommendableOffer]: Resolved offers from both cache and DB, unsorted.
    """
    resolved_offers: list[EnrichedRecommendableOffer] = []

    # --- 1. Split tops vs non-tops ---
    # Only "tops" items are cached: they are the most stable and redundant across requests.
    tops_item_ids: list[str] = [
        iid for iid in multi_venue_item_ids if item_lookup_map[iid].item_origin == ItemOrigin.TOPS
    ]
    non_tops_item_ids: list[str] = [
        iid for iid in multi_venue_item_ids if item_lookup_map[iid].item_origin != ItemOrigin.TOPS
    ]

    # --- 2. Cache lookup for tops items (single MGET round-trip) ---
    cache_hits: dict[str, dict] = {}
    tops_cache_misses: list[str] = tops_item_ids  # default: all tops go to DB
    h3_cell: str | None = None

    if settings.OFFER_RESOLUTION_CACHE_ENABLED and tops_item_ids:
        cache_hits, tops_cache_misses, h3_cell = await _fetch_tops_offer_resolutions_from_cache(
            tops_item_ids, user_context
        )

    items_to_resolve_in_db: list[str] = tops_cache_misses + non_tops_item_ids

    logger.debug(
        "💾 Offer resolution cache lookup.",
        extra={
            "offer_resolution_cache_enabled": settings.OFFER_RESOLUTION_CACHE_ENABLED,
            "multi_venue_total": len(multi_venue_item_ids),
            "tops_items_total": len(tops_item_ids),
            "non_tops_items_total": len(non_tops_item_ids),
            "cache_hits_count": len(cache_hits),
            "cache_misses_count": len(tops_cache_misses),
            "items_sent_to_db": len(items_to_resolve_in_db),
            "db_calls_saved": len(cache_hits),
            "h3_cell": h3_cell,
            "h3_resolution": settings.OFFER_RESOLUTION_CACHE_H3_RESOLUTION
            if settings.OFFER_RESOLUTION_CACHE_ENABLED
            else None,
        },
    )

    # --- 3. Build enriched offers from cache hits (no SQL needed) ---
    cache_hits_skipped_too_far = 0
    for item_id, cached_offer in cache_hits.items():
        item_data = item_lookup_map[item_id]

        # Recompute exact distance from cached venue coordinates (fast, pure Python Haversine)
        distance = calculate_haversine_distance_in_meters(
            user_context.latitude,
            user_context.longitude,
            cached_offer["venue_latitude"],
            cached_offer["venue_longitude"],
        )

        # Guard: skip if the venue falls outside the search radius for this specific user position.
        # (Unlikely with H3 res-8 cells, but protects against zone boundary edge cases.)
        if distance is not None and distance > MAX_DISTANCE_METERS_FOR_OFFER_RETRIEVAL:
            cache_hits_skipped_too_far += 1
            continue

        # Deserialize offer-level dates stored in cache as ISO 8601 strings
        offer_creation_date = (
            datetime.fromisoformat(cached_offer["offer_creation_date"])
            if cached_offer.get("offer_creation_date")
            else None
        )
        stock_beginning_date = (
            datetime.fromisoformat(cached_offer["stock_beginning_date"])
            if cached_offer.get("stock_beginning_date")
            else None
        )

        resolved_offers.append(
            EnrichedRecommendableOffer(
                offer_id=cached_offer["offer_id"],
                item_id=item_id,
                offer_creation_date=offer_creation_date,
                stock_beginning_date=stock_beginning_date,
                is_geolocated=item_data.is_geolocated,
                venue_latitude=cached_offer["venue_latitude"],
                venue_longitude=cached_offer["venue_longitude"],
                offer_user_distance=distance,
                item_score=item_data.item_score,
                item_rank=item_data.item_rank,
                item_origin=item_data.item_origin,
                reco_type=item_data.reco_type,
                semantic_emb_mean=item_data.semantic_emb_mean,
                stock_price=item_data.stock_price,
                category=item_data.category,
                subcategory_id=item_data.subcategory_id,
                search_group_name=item_data.search_group_name,
                booking_number=item_data.booking_number,
                booking_number_last_7_days=item_data.booking_number_last_7_days,
                booking_number_last_14_days=item_data.booking_number_last_14_days,
                booking_number_last_28_days=item_data.booking_number_last_28_days,
            )
        )

    if cache_hits_skipped_too_far > 0:
        logger.debug(
            "⚠️ Cache hits skipped: resolved venue now outside search radius for current user position.",
            extra={"skipped_count": cache_hits_skipped_too_far},
        )

    # --- 4. DB resolution for cache misses + non-tops items ---
    db_rows = []
    if items_to_resolve_in_db:
        logger.debug(
            "🗺️ Resolving multi-venue items via spatial DB query.",
            extra={
                "multi_venue_item_count": len(items_to_resolve_in_db),
                "user_lat": user_context.latitude,
                "user_lng": user_context.longitude,
            },
        )
        db_rows = await find_closest_offers_with_h3_index(
            db, items_to_resolve_in_db, user_context, resolution=settings.GEOSPATIAL_RETRIEVAL_H3_RESOLUTION
        )

    # --- 5. Store newly DB-resolved tops items in cache (single MSET pipeline) ---
    if settings.OFFER_RESOLUTION_CACHE_ENABLED and tops_cache_misses and h3_cell and db_rows:
        await _store_tops_offer_resolutions_in_cache(tops_cache_misses, db_rows, h3_cell)

    # --- 6. Build enriched offers from DB rows ---
    for db_offer, distance in db_rows:
        item_data = item_lookup_map.get(db_offer.item_id)
        if not item_data:
            continue

        resolved_offers.append(
            EnrichedRecommendableOffer(
                offer_id=db_offer.offer_id,
                item_id=db_offer.item_id,
                offer_creation_date=db_offer.offer_creation_date,
                stock_beginning_date=db_offer.stock_beginning_date,
                is_geolocated=item_data.is_geolocated,
                venue_latitude=db_offer.venue_latitude,
                venue_longitude=db_offer.venue_longitude,
                offer_user_distance=float(distance) if distance is not None else None,
                item_score=item_data.item_score,
                item_rank=item_data.item_rank,
                item_origin=item_data.item_origin,
                reco_type=item_data.reco_type,
                semantic_emb_mean=item_data.semantic_emb_mean,
                stock_price=item_data.stock_price,
                category=item_data.category,
                subcategory_id=item_data.subcategory_id,
                search_group_name=item_data.search_group_name,
                booking_number=item_data.booking_number,
                booking_number_last_7_days=item_data.booking_number_last_7_days,
                booking_number_last_14_days=item_data.booking_number_last_14_days,
                booking_number_last_28_days=item_data.booking_number_last_28_days,
            )
        )

    logger.debug(
        "🗺️ Multi-venue items fully resolved.",
        extra={
            "multi_venue_requested": len(multi_venue_item_ids),
            "cache_hits_resolved": len(cache_hits) - cache_hits_skipped_too_far,
            "db_resolved_count": len(db_rows),
            "total_resolved": len(resolved_offers),
        },
    )

    return resolved_offers


async def resolve_closest_venues_from_items(
    db: AsyncSession, candidate_items: list[RecommendableItem], user_context: UserContext
) -> list[EnrichedRecommendableOffer]:
    """
    Transforms abstract ML 'Items' into physical or digital 'Offers', keeping only the closest one.

    This function acts as a smart spatial funnel. To optimize memory and performance,
    it splits candidates into two processing routes (Fast-Track vs Database) to avoid
    loading thousands of duplicate physical offers into RAM.

    Processing Flow:
    1. Routing: Segregates items into a Fast-Track bucket (digital/single venue) and a SQL bucket (multi-venue).
    2. Cache-assisted spatial resolution: delegates multi-venue items to
       _resolve_multi_venue_items, which handles Redis cache lookup/write
       and falls back to a batched spatial SQL query for misses.
    3. Merge & Sort: Combines both buckets and sorts by ascending distance.

    Args:
        db (AsyncSession): The async database session.
        candidate_items (list[RecommendableItem]): Raw items returned by Vertex AI.
        user_context (UserContext): Standardized user context (geo, credit, etc.).

    Returns:
        list[EnrichedRecommendableOffer]: A clean list of fully enriched offers, sorted by distance.
    """
    if not candidate_items:
        return []

    # --- 1. FAST-TRACK & DB ROUTING ---
    fast_track_enriched_offers: list[EnrichedRecommendableOffer] = []
    multi_venue_item_ids: list[str] = []
    item_lookup_map: dict[str, RecommendableItem] = {}
    skipped_no_geo_context = 0
    skipped_too_far = 0

    for item in candidate_items:
        # Route A: Fast-Track (Digital or single-venue physical)
        if not item.is_geolocated or item.total_offers == 1:
            # Reject physical offers if user has no GPS context
            if item.is_geolocated and not user_context.is_geolocated:
                skipped_no_geo_context += 1
                continue

            calculated_distance = None
            if item.is_geolocated and user_context.is_geolocated:
                calculated_distance = calculate_haversine_distance_in_meters(
                    user_context.latitude,
                    user_context.longitude,
                    item.example_venue_latitude,
                    item.example_venue_longitude,
                )

                # Reject if beyond default max radius (100km)
                if calculated_distance is not None and calculated_distance > DEFAULT_MAX_DISTANCE_IN_METERS:
                    skipped_too_far += 1
                    continue

            fast_track_enriched_offers.append(
                EnrichedRecommendableOffer(
                    offer_id=item.example_offer_id,
                    item_id=item.item_id,
                    offer_creation_date=item.offer_creation_date,
                    stock_beginning_date=item.stock_beginning_date,
                    is_geolocated=item.is_geolocated,
                    venue_latitude=item.example_venue_latitude,
                    venue_longitude=item.example_venue_longitude,
                    offer_user_distance=calculated_distance,
                    item_score=item.item_score,
                    item_rank=item.item_rank,
                    item_origin=item.item_origin,
                    reco_type=item.reco_type,
                    semantic_emb_mean=item.semantic_emb_mean,
                    stock_price=item.stock_price,
                    category=item.category,
                    subcategory_id=item.subcategory_id,
                    search_group_name=item.search_group_name,
                    booking_number=item.booking_number,
                    booking_number_last_7_days=item.booking_number_last_7_days,
                    booking_number_last_14_days=item.booking_number_last_14_days,
                    booking_number_last_28_days=item.booking_number_last_28_days,
                )
            )

        # Route B: Cache-assisted spatial resolution (Multi-venue physical items)
        elif user_context.is_geolocated:
            multi_venue_item_ids.append(item.item_id)
            item_lookup_map[item.item_id] = item

    logger.debug(
        "🔀 Venue resolution routing.",
        extra={
            "candidates_in": len(candidate_items),
            "fast_track_count": len(fast_track_enriched_offers),
            "multi_venue_db_count": len(multi_venue_item_ids),
            "skipped_no_geo_context": skipped_no_geo_context,
            "skipped_too_far": skipped_too_far,
        },
    )

    # --- 2. CACHE-ASSISTED SPATIAL RESOLUTION ---
    database_resolved_enriched_offers: list[EnrichedRecommendableOffer] = []

    if multi_venue_item_ids:
        if not user_context.is_geolocated or user_context.latitude is None or user_context.longitude is None:
            logger.debug(
                "⏭️ Skipping spatial DB resolution: user has no GPS context.",
                extra={
                    "multi_venue_item_count": len(multi_venue_item_ids),
                    "is_geolocated": user_context.is_geolocated,
                },
            )
        else:
            database_resolved_enriched_offers = await _resolve_multi_venue_items(
                db=db,
                multi_venue_item_ids=multi_venue_item_ids,
                item_lookup_map=item_lookup_map,
                user_context=user_context,
            )

    # --- 3. MERGE & SORT ---
    final_resolved_offers = fast_track_enriched_offers + database_resolved_enriched_offers

    final_resolved_offers.sort(
        key=lambda x: x.offer_user_distance if x.offer_user_distance is not None else float("inf")
    )

    return final_resolved_offers
