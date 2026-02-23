SHELL:=/bin/bash

install:
	UV_VENV_CLEAR=1 uv venv && uv sync --locked

prepare_db:
	docker compose down -v
	docker compose up -d --wait recommendation_local_db
	@echo "Database is ready and populated!"

start:
	cd src && uv run uvicorn main:app --reload --port 8801

test:
	pytest ./tests

pgcli:
	pgcli -h localhost -p 5439 -u postgres -d db
