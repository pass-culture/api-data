-- Seed test fixtures for Bruno API tests.
-- Idempotent: safe to run before every CI job.
--
-- Prerequisites:
--   psql $DATABASE_URL -f scripts/seed_test_fixtures.sql
--
-- Provides:
--   usr_test_cold_001  — exists in users table, zero listening history  → reco_origin=cold_start
--   All warm-user and warm-offer/artist tests use real IDs from the env vars
--   (user_warm=3196280, offer_warm=28154, artist_warm=a3a7c9f7-...) which must
--   already exist in the staging/dev database.

-- Cold-start user: exists but has no listening history.
-- Adjust table/column names to match your actual schema.
INSERT INTO users (user_id, created_at)
VALUES ('usr_test_cold_001', NOW())
ON CONFLICT (user_id) DO NOTHING;

DELETE FROM booking WHERE user_id = 'usr_test_cold_001';
