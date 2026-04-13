SHELL:=/bin/bash

.PHONY: install start tunnel start-with-remote-db streamlit dev-with-streamlit test access-swagger-api-v1 get-staging-api-token

install:
	@echo "📦 Installing dependencies..."
	UV_VENV_CLEAR=1 uv venv && uv sync --locked

check-gcloud-auth:
	@echo "🔍 Checking gcloud CLI authentication..."
	@gcloud auth print-access-token > /dev/null 2>&1 || (echo "🔐 CLI not authenticated. Launching gcloud auth login..." && gcloud auth login)
	@echo "🔍 Checking Application Default Credentials (ADC) for Python SDKs..."
	@gcloud auth application-default print-access-token > /dev/null 2>&1 || (echo "🔐 ADC not authenticated. Launching gcloud application-default login..." && gcloud auth application-default login)

start: check-gcloud-auth
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

tunnel: check-gcloud-auth
	$(PREPARE_TUNNEL)
	@echo "🔌 Opening standalone SSH tunnel..."
	@source .env && $(SSH_BASE) -L "$$SQL_PORT":"$$REMOTE_SQL_HOST":"$$REMOTE_SQL_PORT"

start-with-remote-db: check-gcloud-auth
	$(PREPARE_TUNNEL)
	@echo "🔌 Establishing SSH tunnel in background..."
	@source .env && $(SSH_BASE) -N -q -L "$$SQL_PORT":"$$REMOTE_SQL_HOST":"$$REMOTE_SQL_PORT" & \
	TUNNEL_PID=$$! ; \
	sleep 2; \
	trap 'echo -e "\n🛑 Stopping API. Closing SSH tunnel (PID: $$TUNNEL_PID)..."; kill $$TUNNEL_PID 2>/dev/null || true' EXIT INT TERM ; \
	$(MAKE) start

streamlit: check-gcloud-auth
	uv run streamlit run streamlit/app.py

dev-with-streamlit: check-gcloud-auth
	$(PREPARE_TUNNEL)
	@echo "🔌 Establishing SSH tunnel in background..."
	@source .env && $(SSH_BASE) -N -q -L "$$SQL_PORT":"$$REMOTE_SQL_HOST":"$$REMOTE_SQL_PORT" & \
	TUNNEL_PID=$$! ; \
	sleep 2; \
	echo "🚀 Starting API in background..." ; \
	uv run src/main.py & \
	API_PID=$$! ; \
	sleep 2; \
	trap 'echo -e "\n🛑 Stopping dev environment. Closing SSH tunnel (PID: $$TUNNEL_PID) and API (PID: $$API_PID)..."; kill $$TUNNEL_PID $$API_PID 2>/dev/null || true' EXIT INT TERM ; \
	echo "🎨 Starting Streamlit..." ; \
	$(MAKE) streamlit

test:
	@echo "🧪 Running unit tests..."
	uv run pytest tests


define PREPARE_SWAGGER_TUNNEL
	@source .env && \
	REQUIRED_VARS=("GCP_ZONE" "GCP_IAP_BASTION_INSTANCE_NAME" "REMOTE_SQL_GCP_PROJECT" "RECOMMENDATION_V1_STAGING_SOCKS_PORT" "RECOMMENDATION_V1_STAGING_CLOUDRUN_URL"); \
	for var in "$${REQUIRED_VARS[@]}"; do \
	   if [ -z "$${!var}" ]; then echo "❌ Error: $$var is missing in .env"; exit 1; fi; \
	done; \
	echo "🧹 Cleaning up port $$RECOMMENDATION_V1_STAGING_SOCKS_PORT..." && \
	lsof -ti:$$RECOMMENDATION_V1_STAGING_SOCKS_PORT | xargs kill -9 2>/dev/null || true
endef

UNAME_S := $(shell uname -s)

ifeq ($(UNAME_S),Linux)
    CHROME_BIN := google-chrome
else ifeq ($(UNAME_S),Darwin)
    CHROME_BIN := /Applications/Google Chrome.app/Contents/MacOS/Google Chrome
endif

access-swagger-api-v1: check-gcloud-auth
	$(PREPARE_SWAGGER_TUNNEL)
	@echo "🔌 Opening SOCKS tunnel to legacy V1 infrastructure..."
	@source .env && $(SSH_BASE) -N -D "$$RECOMMENDATION_V1_STAGING_SOCKS_PORT" & \
	TUNNEL_PID=$$! ; \
	echo "⏳ Waiting for tunnel initialization..." ; \
	sleep 3 ; \
	echo "🔄 Tunnel might need more time. If the page fails to load, please refresh the window." ; \
	echo "🚀 Opening Google Chrome with SOCKS proxy..." ; \
	source .env && "$(CHROME_BIN)" \
		--proxy-server="socks5://localhost:$$RECOMMENDATION_V1_STAGING_SOCKS_PORT" \
		--user-data-dir="/tmp/chrome_proxy_tmp" \
		--no-first-run \
		--no-default-browser-check \
		"$$RECOMMENDATION_V1_STAGING_CLOUDRUN_URL" \
		> /dev/null 2>&1 & \
	echo "✅ Connected. Press Ctrl+C to close the tunnel." ; \
	trap "kill $$TUNNEL_PID" INT TERM EXIT; \
	wait $$TUNNEL_PID

get-staging-api-token: check-gcloud-auth
	@source .env && \
	if [ -z "$$GCP_SECRET_PROJECT" ] || [ -z "$$API_RECO_TOKEN_SECRET_NAME" ]; then \
		echo "❌ Error: GCP_SECRET_PROJECT or API_RECO_TOKEN_SECRET_NAME is missing from .env"; \
		exit 1; \
	fi; \
	echo "🔐 Fetching API token..." && \
	gcloud secrets versions access latest --secret "$$API_RECO_TOKEN_SECRET_NAME" --project "$$GCP_SECRET_PROJECT"
