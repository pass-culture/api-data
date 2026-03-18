SHELL:=/bin/bash

install:
	UV_VENV_CLEAR=1 uv venv && uv sync --locked

create_tables:
	PYTHONPATH=src API_LOCAL=1 python src/scripts/create_tables.py

prepare_db:
	docker compose down -v
	docker compose up -d testdb
	@wait_for_db_to_be_up() { \
		while ! docker compose exec testdb pg_isready -U postgres; do \
			echo "Waiting for DB to be ready..."; \
			sleep 1; \
		done; \
	}; \
	wait_for_db_to_be_up
	@echo "Database is up, waiting 2 seconds for stabilization..."
	@sleep 2

start: prepare_db create_tables
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
