# Database Flow Diagram for `/playlist_recommendation/{user_id}` Route

## Overview
This diagram explains all database interactions when calling the `/playlist_recommendation/{user_id}` route in the recommendation API.

```mermaid
graph TD
    A[GET /playlist_recommendation/user_id] --> B[UserContextDB.get_user_context]
    A --> C[Offer.parse_offer_list]
    A --> D[ModelEngineFactory.handle_prediction]

    %% User Context Flow
    B --> B1[Iris.get_iris_from_coordinates]
    B1 --> B1_DB[(DB Query: iris_france table<br/>ST_Contains for coordinates)]
    B1_DB --> B1_Result[Returns iris_id]

    B --> B2[UserContextDB.get_user_profile]
    B2 --> B2_DB[(DB Query: enriched_user table<br/>SELECT user stats by user_id)]
    B2_DB --> B2_Result[Returns age, bookings_count,<br/>clicks_count, favorites_count,<br/>deposit_remaining_credit]

    B1_Result --> B_Final[UserContext object]
    B2_Result --> B_Final

    %% Offer Parsing Flow
    C --> C1[For each offer_id: Offer.get_offer_characteristics]
    C1 --> C1a[Offer.get_item]
    C1a --> C1a_DB[(DB Query: item_ids table<br/>SELECT by offer_id)]
    C1a_DB --> C1a_Result[Returns item characteristics<br/>venue_latitude, venue_longitude]

    C1a_Result --> C1b[Iris.get_iris_from_coordinates<br/>for offer location]
    C1b --> C1b_DB[(DB Query: iris_france table<br/>ST_Contains for offer coordinates)]
    C1b_DB --> C1_Final[List of Offer objects]

    %% Model Engine Flow
    D --> D1[ModelEngine.get_scoring]
    D1 --> D2[OfferScorer.get_scoring]
    D2 --> D3[get_non_recommendable_items]
    D3 --> D3_DB[(DB Query: non_recommendable_items table<br/>SELECT item_ids for user_id)]
    D3_DB --> D3_Result[List of excluded item_ids]

    D2 --> D4[OfferScorer.get_nearest_offers]
    D4 --> D5[RecommendableOfferDB.get_nearest_offers]
    D5 --> D5_DB[(DB Query: recommendable_offers_raw table<br/>Complex geospatial query with ST_Distance<br/>ORDER BY distance/booking_number)]
    D5_DB --> D5_Result[Ranked offers with distances]

    %% Final Assembly
    B_Final --> E[Assemble Response]
    C1_Final --> E
    D5_Result --> E
    E --> F[Return JSON Response]

    %% Styling
    classDef dbQuery fill:#e1f5fe,stroke:#0277bd,stroke-width:2px
    classDef process fill:#f3e5f5,stroke:#7b1fa2,stroke-width:2px
    classDef result fill:#e8f5e8,stroke:#2e7d32,stroke-width:2px

    class B1_DB,B2_DB,C1a_DB,C1b_DB,D3_DB,D5_DB dbQuery
    class B,C,D,D1,D2,D4,D5 process
    class B_Final,C1_Final,D3_Result,D5_Result,F result
```

## Database Tables Accessed

### 1. **iris_france** table
- **Purpose**: Convert geographic coordinates (latitude/longitude) to IRIS administrative codes
- **Queries**:
  - For user location: `ST_Contains(shape, POINT(longitude, latitude))`
  - For each input offer location: Same spatial query
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
- **Purpose**: Get offer characteristics including venue coordinates
- **Query**: `SELECT * WHERE offer_id = ?` (for each input offer)
- **Returns**: item_id, venue_latitude, venue_longitude, booking_number, is_sensitive
- **Used by**: `Offer.get_item()`

### 4. **non_recommendable_items** table
- **Purpose**: Filter out items that shouldn't be recommended to the user
- **Query**: `SELECT item_id WHERE user_id = ?`
- **Used by**: `get_non_recommendable_items()`

### 5. **recommendable_offers_raw** table
- **Purpose**: Find the nearest available offers for recommendation
- **Query**: Complex geospatial query using:
  - `ST_Distance()` for distance calculation
  - Window functions with `ROW_NUMBER()` for ranking
  - Filtering by item_ids from ML model predictions
  - Ordering by distance or booking popularity
- **Used by**: `RecommendableOfferDB.get_nearest_offers()`

## Key Database Interaction Points

1. **User Context Building** (2 queries)
   - Geographic location → IRIS code
   - User profile data retrieval

2. **Input Offer Processing** (2×N queries, where N = number of input offers)
   - Offer characteristics lookup
   - Geographic location → IRIS code for each offer

3. **Recommendation Filtering** (1 query)
   - Exclude non-recommendable items for the user

4. **Final Offer Selection** (1 complex query)
   - Geospatial distance calculation and ranking
   - Combines ML predictions with geographic and popularity data

## Performance Considerations

- **Caching**: The system uses caching for `recommendable_offers` to avoid repeated complex queries
- **Geospatial Queries**: Heavy use of PostGIS spatial functions (`ST_Contains`, `ST_Distance`)
- **Query Complexity**: The final recommendation query is the most complex, involving window functions and spatial calculations
- **Query Count**: Total queries ≈ 5 + (2 × number_of_input_offers)

## Summary

The route performs approximately **5-10 database queries** depending on the number of input offers:
- **2 queries** for user context (location + profile)
- **2×N queries** for input offer processing (N = number of input offers)
- **1 query** for filtering non-recommendable items
- **1 complex query** for finding and ranking nearest recommendable offers

The most database-intensive part is the final recommendation scoring, which involves complex geospatial calculations to find the nearest relevant offers based on ML model predictions.
