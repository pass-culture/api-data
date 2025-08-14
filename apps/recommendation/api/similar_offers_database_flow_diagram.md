# Database Flow Diagram for `/similar_offers/{offer_id}` Route

## Overview

This diagram explains all database interactions when calling the `/similar_offers/{offer_id}` route in the recommendation API. This route finds offers similar to a specific input offer.

```mermaid
graph TD
    A[GET /similar_offers/offer_id] --> B[UserContextDB.get_user_context]
    A --> C[Offer.parse_offer_list<br/>with input offer_id]
    A --> D[ModelEngineFactory.handle_prediction<br/>context = similar_offer]

    %% User Context Flow (same as playlist_recommendation)
    B --> B1[Iris.get_iris_from_coordinates]
    B1 --> B1_DB[(DB Query: iris_france table<br/>ST_Contains for coordinates)]
    B1_DB --> B1_Result[Returns iris_id]

    B --> B2[UserContextDB.get_user_profile]
    B2 --> B2_DB[(DB Query: enriched_user table<br/>SELECT user stats by user_id)]
    B2_DB --> B2_Result[Returns age, bookings_count,<br/>clicks_count, favorites_count,<br/>deposit_remaining_credit]

    B1_Result --> B_Final[UserContext object]
    B2_Result --> B_Final

    %% Input Offer Processing (for the target offer)
    C --> C1[Offer.get_offer_characteristics<br/>for target offer_id]
    C1 --> C1a[Offer.get_item]
    C1a --> C1a_DB[(DB Query: item_ids table<br/>SELECT by offer_id)]
    C1a_DB --> C1a_Result[Returns target offer characteristics<br/>venue_latitude, venue_longitude, item_id]

    C1a_Result --> C1b[Iris.get_iris_from_coordinates<br/>for target offer location]
    C1b --> C1b_DB[(DB Query: iris_france table<br/>ST_Contains for offer coordinates)]
    C1b_DB --> C1_Final[Target Offer object]

    %% Model Engine Flow - Similar Offers Logic
    D --> D1[SimilarOffer.get_scoring<br/>OR Recommendation.get_scoring<br/>based on offer sensitivity]
    D1 --> D2[OfferScorer.get_scoring]
    D2 --> D3[get_non_recommendable_items]
    D3 --> D3_DB[(DB Query: non_recommendable_items table<br/>SELECT item_ids for user_id)]
    D3_DB --> D3_Result[List of excluded item_ids]

    D2 --> D4[OfferScorer.get_nearest_offers<br/>with similarity-based filtering]
    D4 --> D5[RecommendableOfferDB.get_nearest_offers<br/>filtered by similarity to target offer]
    D5 --> D5_DB[(DB Query: recommendable_offers_raw table<br/>Complex geospatial + similarity query<br/>using target offer characteristics)]
    D5_DB --> D5_Result[Similar offers ranked by<br/>distance + similarity score]

    %% Final Assembly
    B_Final --> E[Assemble Response]
    C1_Final --> E
    D5_Result --> E
    E --> F[Return JSON Response<br/>with similar offers]

    %% Styling
    classDef dbQuery fill:#e1f5fe,stroke:#0277bd,stroke-width:2px
    classDef process fill:#f3e5f5,stroke:#7b1fa2,stroke-width:2px
    classDef result fill:#e8f5e8,stroke:#2e7d32,stroke-width:2px
    classDef similarLogic fill:#fff3e0,stroke:#f57c00,stroke-width:2px

    class B1_DB,B2_DB,C1a_DB,C1b_DB,D3_DB,D5_DB dbQuery
    class B,C,D,D1,D2,D4,D5 process
    class B_Final,C1_Final,D3_Result,D5_Result,F result
    class D1,D4,D5 similarLogic
```

## Database Tables Accessed

### 1. **iris_france** table

- **Purpose**: Convert geographic coordinates (latitude/longitude) to IRIS administrative codes
- **Queries**:
  - For user location: `ST_Contains(shape, POINT(longitude, latitude))`
  - For target offer location: Same spatial query
- **Used by**: `Iris.get_iris_from_coordinates()`

### 2. **enriched_user** table

- **Purpose**: Get user profile information and behavior statistics
- **Query**:

  ```sql
  SELECT user_id,
         date_part('year', age(user_birth_date)) as age,
         coalesce(booking_cnt, 0) as bookings_count,
         coalesce(consult_offer, 0) as clicks_count,
         coalesce(has_added_offer_to_favorites, 0) as favorites_count,
         coalesce(user_theoretical_remaining_credit, user_deposit_initial_amount) as user_deposit_remaining_credit
  WHERE user_id = ?
  ```

- **Used by**: `UserContextDB.get_user_profile()`

### 3. **item_ids** table

- **Purpose**: Get target offer characteristics for similarity comparison
- **Query**: `SELECT * WHERE offer_id = ?` (for the target offer)
- **Returns**: item_id, venue_latitude, venue_longitude, booking_number, is_sensitive
- **Used by**: `Offer.get_item()`

### 4. **non_recommendable_items** table

- **Purpose**: Filter out items that shouldn't be recommended to the user
- **Query**: `SELECT item_id WHERE user_id = ?`
- **Used by**: `get_non_recommendable_items()`

### 5. **recommendable_offers_raw** table

- **Purpose**: Find offers similar to the target offer
- **Query**: Complex similarity-based query using:
  - Target offer characteristics for similarity filtering
  - `ST_Distance()` for geographic proximity
  - Window functions with `ROW_NUMBER()` for ranking
  - Filtering by categories/subcategories if specified
  - Ordering by similarity score and distance
- **Used by**: `RecommendableOfferDB.get_nearest_offers()`

## Key Differences from `/playlist_recommendation`

### 1. **Model Selection Logic**

- **Similar Offers**: Uses `SimilarOffer` model engine by default
- **Fallback**: Falls back to `Recommendation` model if target offer is sensitive or no input offers
- **Context**: Uses `"similar_offer"` context instead of `"recommendation"`

### 2. **Target Offer Processing**

- **Single Offer Focus**: Processes only ONE target offer (the `offer_id` in the URL)
- **Similarity Baseline**: Target offer characteristics become the baseline for similarity scoring
- **Category Filtering**: Can filter by categories/subcategories related to the target offer

### 3. **Retrieval Strategy**

- **Similarity-based**: ML model focuses on finding items similar to the target offer
- **Geographic + Content**: Combines geographic proximity with content-based similarity
- **Playlist Type**: Uses `GetSimilarOfferPlaylistParams` with specialized playlist types:
  - `sameCategorySimilarOffers`
  - `sameSubCategorySimilarOffers`
  - `otherCategoriesSimilarOffers`
  - `GenericSimilarOffers`

## Database Query Pattern

The route performs approximately **5-6 database queries**:

1. **User Context Queries (2 queries)**:
   - Geographic location → IRIS code
   - User profile data retrieval

2. **Target Offer Processing (2 queries)**:
   - Target offer characteristics lookup
   - Geographic location → IRIS code for target offer

3. **Recommendation Filtering (1 query)**:
   - Exclude non-recommendable items for the user

4. **Similar Offers Selection (1 complex query)**:
   - Similarity-based geospatial query using target offer as baseline
   - Ranking by similarity score and geographic proximity

## Performance Considerations

- **Similarity Computation**: Uses ML model endpoints to compute content-based similarity
- **Geographic Filtering**: Still uses PostGIS spatial functions for location-based filtering
- **Caching**: Uses the same caching mechanism as playlist recommendations
- **Target Offer Dependency**: Performance depends on the characteristics of the target offer
- **Query Complexity**: Similar complexity to playlist recommendations but with different ranking criteria

## Summary

The `/similar_offers/{offer_id}` route has a **similar database access pattern** to `/playlist_recommendation` but with key differences:

- **Purpose**: Find offers similar to a specific target offer vs. general user recommendations
- **Query Count**: ~5-6 queries (slightly fewer since only one input offer)
- **Model Logic**: Uses similarity-based ML models with target offer as reference point
- **Ranking**: Prioritizes content similarity over pure geographic proximity
- **Fallback**: Can fall back to general recommendations if target offer is problematic

The most database-intensive part remains the final similarity search, which combines ML-based similarity scoring with geospatial calculations to find the best matching offers.
