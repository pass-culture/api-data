CREATE TABLE past_offer_context (
    id SERIAL PRIMARY KEY,
    user_id VARCHAR(256),
    offer_id VARCHAR(256),
    call_id VARCHAR(256),
    context VARCHAR(256),
    context_extra_data JSON,
    date TIMESTAMP WITH TIME ZONE,
    user_bookings_count DOUBLE PRECISION,
    user_clicks_count DOUBLE PRECISION,
    user_favorites_count DOUBLE PRECISION,
    user_deposit_remaining_credit DOUBLE PRECISION,
    user_iris_id VARCHAR(256),
    user_is_geolocated BOOLEAN,
    user_latitude DOUBLE PRECISION,
    user_longitude DOUBLE PRECISION,
    user_extra_data JSON,
    offer_user_distance DOUBLE PRECISION,
    offer_is_geolocated BOOLEAN,
    offer_item_id VARCHAR(256),
    offer_booking_number DOUBLE PRECISION,
    offer_stock_price DOUBLE PRECISION,
    offer_creation_date TIMESTAMP,
    offer_stock_beginning_date TIMESTAMP,
    offer_category VARCHAR(256),
    offer_subcategory_id VARCHAR(256),
    offer_item_rank DOUBLE PRECISION,
    offer_item_score DOUBLE PRECISION,
    offer_order DOUBLE PRECISION,
    offer_venue_id VARCHAR(256),
    offer_extra_data JSON
);


ALTER TABLE past_offer_context ALTER COLUMN id TYPE BIGINT;
ALTER SEQUENCE past_offer_context_id_seq AS BIGINT MAXVALUE 9223372036854775807 CYCLE;