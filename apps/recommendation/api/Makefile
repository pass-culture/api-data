SHELL:=/bin/bash

SSH_BASE = gcloud compute ssh --zone "$$GCP_ZONE" "$$GCP_IAP_BASTION_INSTANCE_NAME" --tunnel-through-iap --project "$$REMOTE_SQL_GCP_PROJECT" --

define PREPARE_TUNNEL
	@source .env && \
	REQUIRED_VARS=("GCP_ZONE" "GCP_IAP_BASTION_INSTANCE_NAME" "REMOTE_SQL_GCP_PROJECT" "SQL_PORT" "REMOTE_SQL_HOST" "REMOTE_SQL_PORT"); \
	for var in "$${REQUIRED_VARS[@]}"; do \
	   if [ -z "$${!var}" ]; then echo "❌ Error: $$var is missing in .env"; exit 1; fi; \
	done; \
	echo "🧹 Cleaning up port $$SQL_PORT..." && \
	lsof -ti:$$SQL_PORT | xargs kill -9 2>/dev/null || true
endef

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


start-with-remote-db:
	$(PREPARE_TUNNEL)
	@echo "🔌 Establishing SSH tunnel in background..."
	@source .env && $(SSH_BASE) -N -q -L "$$SQL_PORT":"$$REMOTE_SQL_HOST":"$$REMOTE_SQL_PORT" & \
	TUNNEL_PID=$$! ; \
	sleep 2; \
	trap 'echo -e "\n🛑 Stopping API. Closing SSH tunnel (PID: $$TUNNEL_PID)..."; kill $$TUNNEL_PID 2>/dev/null || true' EXIT INT TERM ; \
	cd src && API_LOCAL=1 uv run uvicorn main:app --reload --env-file ../.env

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

build_and_run_locally_in_docker:
	cp ~/.config/gcloud/application_default_credentials.json src/
	docker build . -t reco_v1 --build-arg LOCAL=true
	rm src/application_default_credentials.json
	docker run -p 8080:8080 reco_v1_fix:latest -e API_LOCAL=true
