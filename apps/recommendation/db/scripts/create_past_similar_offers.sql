CREATE TABLE past_similar_offers (
    id              SERIAL PRIMARY KEY,
    user_id         int,
    origin_offer_id int,
    offer_id        int,
    date            timestamp with time zone,
    group_id        varchar,
    model_name      varchar,
    model_version   varchar,
    call_id         varchar,
    reco_filters    json,
    venue_iris_id   varchar
);

ALTER TABLE past_similar_offers ALTER COLUMN id TYPE BIGINT;
ALTER SEQUENCE past_similar_offers_id_seq AS BIGINT MAXVALUE 9223372036854775807 CYCLE;
