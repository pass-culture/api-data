# Offer Page Playlists

The `/offer_page_playlists/{offer_id}` endpoint returns all the "similar offer" playlists
displayed on an offer detail page in a single round-trip. The number, title, and retrieval
strategy of each playlist depend on the `search_group_name` (category) of the reference offer.

> ⚠️ **Single source of truth**: this entire logic is implemented in the
> `build_similar_offer_playlist_configs` function
> (`src/controllers/pipeline_offer_page_playlists.py`). This document is only a human-readable
> summary of that function. **If `build_similar_offer_playlist_configs` is modified (new
> category rule, new playlist, new retrieval model, etc.), this documentation must be updated
> in the same change** to stay accurate.

## Playlist composition rules

### Books & Music (`LIVRES`, `MUSIQUE`)

Two playlists targeting the **same category**, using two different retrieval models:

| Order | Title | Type | Retrieval model | Scope |
| --- | --- | --- | --- | --- |
| 1 | "Les fans aiment aussi" | `same_type_coreservation` | Coreservation | Same category |
| 2 | "Dans la même catégorie" | `same_type_graph` | Graph | Same category |

### All other categories

One same-type playlist and one cross-type playlist:

| Order | Title | Type | Retrieval model | Scope |
| --- | --- | --- | --- | --- |
| 1 | "Les fans aiment aussi" | `same_type` | Coreservation | Same category |
| 2 | "Ça peut aussi te plaire" | `cross_type` | Coreservation | All other categories |

> When the offer's `search_group_name` is `NONE` (e.g. offer not found or category unknown),
> the "same type" playlist uses `NONE` as its scope, and the cross-type playlist covers
> **all** known categories.
