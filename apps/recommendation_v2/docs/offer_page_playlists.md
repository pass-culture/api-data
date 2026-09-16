# Offer Page Playlists (`/offer_page_playlists/{offer_id}`)

This endpoint returns all recommendation playlists to display on an offer detail page in a single round-trip.

The recommendation API resolves the offer's category (`search_group_name`) directly from the `offer_metadata_mv` database table.
If the offer is not found in the database (e.g., created after the latest daily database sync), the endpoint returns HTTP 404 Not Found.

## Playlist Composition Rules

### Books (`LIVRES`) and Music (`MUSIQUE`)

Two same-type playlists with different retrieval models:

| Order | Title | Retrieval model | Scope | Analytics type (`analytics_playlist_type`) |
| --- | --- | --- | --- | --- |
| 1 | "Les fans aiment aussi" | Coreservation | Same category | `sameCategorySimilarOffers` |
| 2 | "Dans la même catégorie" | Graph | Same category | `booksSameCategorySimilarOffers` for `LIVRES`, `sameCategorySimilarOffers` for `MUSIQUE` |

### All other categories

One same-type playlist and one cross-type playlist:

| Order | Title | Retrieval model | Scope | Analytics type (`analytics_playlist_type`) |
| --- | --- | --- | --- | --- |
| 1 | "Les fans aiment aussi" | Coreservation | Same category | `sameCategorySimilarOffers` |
| 2 | "Ça peut aussi te plaire" | Coreservation | All other categories | `otherCategoriesSimilarOffers` |

## Legacy analytics mapping (`analytics_playlist_type`)

Each playlist item exposed by the API carries an `analytics_playlist_type` value (`AnalyticsPlaylistTypeEnum`, `src/schemas/offer_page_playlists.py`), reproducing the legacy analytics tag so existing Firebase dashboards/funnels keep working unchanged:

- `sameCategorySimilarOffers`: same-category playlist, for every case except the `LIVRES` graph playlist.
- `booksSameCategorySimilarOffers`: same-category playlist retrieved with the graph model, for `LIVRES` offers only.
- `otherCategoriesSimilarOffers`: cross-category playlist.
