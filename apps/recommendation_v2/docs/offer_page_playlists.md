# Offer Page Playlists (`/offer_page_playlists/{offer_id}`)

This endpoint returns all recommendation playlists to display on an offer detail page in a single round-trip.

The recommendation API resolves the offer's category (`search_group_name`) directly from the `offer_metadata_mv` database table.
If the offer is not found in the database (e.g., created after the latest daily database sync), the endpoint returns HTTP 404 Not Found.

## Playlist Composition Rules

### Books (`LIVRES`) and Music (`MUSIQUE`)

Two same-type playlists with different retrieval models:

| Order | Title | Retrieval model | Scope | Analytics type (`analytics_playlist_type`) |
| --- | --- | --- | --- | --- |
| 1 | "Les fans aiment aussi" | Coreservation | Same category | `sameCategorySimilarOffersTwoTower` |
| 2 | "Dans la même catégorie" | Graph | Same category | `sameCategorySimilarOffersGraph` |

### All other categories

One same-type playlist and one cross-type playlist:

| Order | Title | Retrieval model | Scope | Analytics type (`analytics_playlist_type`) |
| --- | --- | --- | --- | --- |
| 1 | "Les fans aiment aussi" | Coreservation | Same category | `sameCategorySimilarOffersTwoTower` |
| 2 | "Ça peut aussi te plaire" | Coreservation | All other categories | `otherCategoriesSimilarOffersTwoTower` |

## Legacy analytics mapping (`analytics_playlist_type`)

Each playlist item exposed by the API carries an `analytics_playlist_type` value (`AnalyticsPlaylistTypeEnum`, `src/schemas/offer_page_playlists.py`), encoding both the playlist scope (same/other category) and the retrieval model ("two tower" i.e. coreservation, or graph):

- `sameCategorySimilarOffersTwoTower`: same-category playlist retrieved with the "two tower" (coreservation) model.
- `sameCategorySimilarOffersGraph`: same-category playlist retrieved with the graph model.
- `otherCategoriesSimilarOffersTwoTower`: cross-category playlist retrieved with the "two tower" (coreservation) model.

## Parallel Generation, Balanced Deduplication & Tracking

1. **Parallel generation**: Both playlists are generated concurrently via `asyncio.gather`, each using its own dedicated `AsyncSession`.
2. **Balanced cross-playlist deduplication (`deduplicate_and_balance_playlists`)**:
   - Any `offer_id` appearing in both playlists is removed from one of them so an offer never appears twice on the same page.
   - Duplicate offers are sorted by relative rank difference (`pos_1 - pos_2` descending) so that each playlist preferentially drops offers ranked worse in that playlist.
   - Removals first reduce any length difference between the two playlists (dropping from the longer playlist), then split remaining duplicate pairs evenly (`1` per playlist) once both playlists have the same size.
   - If a single odd duplicate remains when both playlists have equal length, it is removed from the playlist where its position index is worse (`pos_1 > pos_2` → remove from playlist 1; `pos_2 > pos_1` → remove from playlist 2), or from **playlist 2** if `pos_1 == pos_2`.
3. **Post-deduplication BigQuery tracking (`log_past_offer_context_to_sink`)**:
   - Tracking logs are deferred during sub-pipeline execution and flushed only after deduplication so that BigQuery records solely the offers actually displayed to the user, with accurate 0-based `offer_order` positions.
