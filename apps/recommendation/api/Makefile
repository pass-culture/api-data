SHELL:=/bin/bash

install:
	UV_VENV_CLEAR=1 uv venv && uv sync --locked

start:
	cd src && API_LOCAL=1 uv run uvicorn main:app --reload

test:
	docker compose down -v
	docker compose up -d
	@wait_for_db_to_be_up() { \
		while ! docker compose exec testdb pg_isready -U postgres; do \
			sleep 1; \
		done; \
	}; \
	create_db_db() { \
		docker compose exec testdb psql -U postgres -c "DROP DATABASE db;"; \
		docker compose exec testdb psql -U postgres -c "CREATE DATABASE db;"; \
		docker compose exec testdb psql -U postgres -d db -c "CREATE EXTENSION postgis;"; \
	}; \
	wait_for_db_to_be_up && create_db_db
	API_LOCAL=1 uv run pytest
	docker compose down -v
