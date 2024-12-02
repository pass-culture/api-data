CREATE TABLE past_similar_offers (
    id              SERIAL PRIMARY KEY,
    user_id         INT NOT NULL,
    origin_offer_id INT NOT NULL,
    offer_id        INT NOT NULL,
    date            TIMESTAMP WITH TIME ZONE NOT NULL,
    group_id        VARCHAR2(255),
    model_name      VARCHAR2(255) NOT NULL,
    model_version   VARCHAR2(50) NOT NULL,
    call_id         VARCHAR2(100) NOT NULL,
    reco_filters    JSON,
    venue_iris_id   VARCHAR2(100) NOT NULL
);

ALTER TABLE past_similar_offers ALTER COLUMN id TYPE BIGINT;

ALTER SEQUENCE past_similar_offers_id_seq AS BIGINT
    MAXVALUE 9223372036854775807 CYCLE;
