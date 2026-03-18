SHELL:=/bin/bash

install:
	@echo "📦 Installing dependencies..."
	UV_VENV_CLEAR=1 uv venv && uv sync --locked

start:
	uv run src/main.py


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

tunnel:
	$(PREPARE_TUNNEL)
	@echo "🔌 Opening standalone SSH tunnel..."
	@source .env && $(SSH_BASE) -L "$$SQL_PORT":"$$REMOTE_SQL_HOST":"$$REMOTE_SQL_PORT"

start-with-remote-db:
	$(PREPARE_TUNNEL)
	@echo "🔌 Establishing SSH tunnel in background..."
	@source .env && $(SSH_BASE) -N -q -L "$$SQL_PORT":"$$REMOTE_SQL_HOST":"$$REMOTE_SQL_PORT" & \
	TUNNEL_PID=$$! ; \
	sleep 2; \
	trap 'echo -e "\n🛑 Stopping API. Closing SSH tunnel (PID: $$TUNNEL_PID)..."; kill $$TUNNEL_PID 2>/dev/null || true' EXIT INT TERM ; \
	$(MAKE) start

test:
	pytest ./tests
