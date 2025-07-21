SHELL:=/bin/bash

install:
	uv venv -p 3.9 && uv pip install -r requirements.txt

start:
	source .venv/bin/activate && cd src && API_LOCAL=1 uvicorn main:app --reload

compile_requirements:
	source .venv/bin/activate && uv pip compile requirements.in

test:
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
	API_LOCAL=1 pytest
	docker compose down -v
