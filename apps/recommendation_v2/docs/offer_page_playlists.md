# Offer Page Playlists

The `/offer_page_playlists/{offer_id}` endpoint returns all the "similar offer" playlists
displayed on an offer detail page in a single round-trip. The number, title, and retrieval
strategy of each playlist depend on the `search_group_name` (category) of the reference offer.

> ⚠️ **Single source of truth**: this entire logic is implemented in the
> `build_similar_offer_playlist_configs` function
> (`src/controllers/pipeline_offer_page_playlists.py`). This document is only a human-readable
> summary of that function. **If `build_similar_offer_playlist_configs` is modified (new
> category rule, new playlist, new retrieval model, etc.), this documentation must be updated
> in the same change.**

## Playlist composition rules

### Books & Music (`LIVRES`, `MUSIQUE`)

Two playlists targeting the **same category**, using two different retrieval models:

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

> When the offer's `search_group_name` is `NONE` (e.g. offer not found or category unknown),
> the "same type" playlist uses `NONE` as its scope, and the cross-type playlist covers
> **all** known categories.

## Legacy analytics mapping (`analytics_playlist_type`)

Each playlist item exposed by the API carries an `analytics_playlist_type` value
(`AnalyticsPlaylistTypeEnum`, `src/schemas/offer_page_playlists.py`), reproducing the
`similar_offer_playlist_type` Firebase event property that the client used to send on its own.
This field was never sent to the backend: before this endpoint existed, the client-side
implementation itself decided which "similar offer" playlists to build (which filters/category
to query, which retrieval model to use) and, consequently, controlled the value of this
analytics tag. Now that the backend decides which playlists to generate and return, it must
reproduce these same legacy values so existing Firebase dashboards/funnels keep working
unchanged:

- `sameCategorySimilarOffers`: same-category playlist, for every case **except** the
  `LIVRES` graph playlist (see below). This covers the standard same-category playlist,
  the LIVRES/MUSIQUE coreservation playlist, and the MUSIQUE graph playlist (music never
  had a dedicated legacy tag).
- `booksSameCategorySimilarOffers`: same-category playlist retrieved with the graph
  model, **for `LIVRES` offers only**. The legacy client-side component that emitted this
  tag unconditionally forced `search_group_names=[LIVRES]` and the graph retrieval model,
  regardless of the actual offer category, and was never used for `MUSIQUE`.
- `otherCategoriesSimilarOffers`: cross-category playlist.
