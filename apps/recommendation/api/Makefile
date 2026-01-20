SHELL:=/bin/bash

install:
	UV_VENV_CLEAR=1 uv venv && uv sync --locked

create_tables:
	PYTHONPATH=src API_LOCAL=1 python src/scripts/create_tables.py

seed_db:
	PYTHONPATH=src API_LOCAL=1 python src/scripts/seed_db.py

prepare_db:
	docker compose down -v
	docker compose up -d testdb
	@wait_for_db_to_be_up() { \
		while ! docker compose exec testdb pg_isready -U postgres; do \
			echo "Waiting for DB to be ready..."; \
			sleep 1; \
		done; \
	}; \
	create_db_db() { \
		echo "Dropping and creating database db..."; \
		docker compose exec testdb psql -U postgres -c "DROP DATABASE IF EXISTS db;"; \
		docker compose exec testdb psql -U postgres -c "CREATE DATABASE db;"; \
		docker compose exec testdb psql -U postgres -d db -c "CREATE EXTENSION IF NOT EXISTS postgis;"; \
	}; \
	wait_for_db_to_be_up && create_db_db
	@echo "Database is up, waiting 2 seconds for stabilization..."
	@sleep 2

start: prepare_db create_tables seed_db
	cd src && API_LOCAL=1 uv run uvicorn main:app --reload

test:
	@$(MAKE) prepare_db
	API_LOCAL=1 pytest
	docker compose down -v


ruff_fix:
	uv run ruff check --fix
	uv run ruff format

ruff_check:
	uv run ruff check
	uv run ruff format --check
