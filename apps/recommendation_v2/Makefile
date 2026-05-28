SHELL:=/bin/bash

.PHONY: install start tunnel start-with-remote-db streamlit streamlit-remote dev-with-streamlit test access-remote-swagger get-staging-api-token show-config

# Helper: load .env then optionally override with .env.<DEPLOY_ENV>
# Usage: make <target> DEPLOY_ENV=dev|stg|prod
# NOTE: we use DEPLOY_ENV (not ENV) to avoid collision with the app's ENV variable (used by settings.py)
DEPLOY_ENV ?=
define load_env_cmd
	source .env $(if $(DEPLOY_ENV),&& [ -f .env.$(DEPLOY_ENV) ] && source .env.$(DEPLOY_ENV) || true,)
endef

install:
	@echo "📦 Installing dependencies..."
	UV_VENV_CLEAR=1 uv venv && uv sync --locked

check-gcloud-auth:
	@echo "🔍 Checking gcloud CLI authentication..."
	@gcloud auth print-access-token > /dev/null 2>&1 || (echo "🔐 CLI not authenticated. Launching gcloud auth login..." && gcloud auth login)
	@echo "🔍 Checking Application Default Credentials (ADC) for Python SDKs..."
	@gcloud auth application-default print-access-token > /dev/null 2>&1 || (echo "🔐 ADC not authenticated. Launching gcloud application-default login..." && gcloud auth application-default login)

start-redis:
	@echo "🚀 Starting local Redis container..."
	@docker start reco-redis 2>/dev/null || docker run -d --name reco-redis -p 6379:6379 redis:alpine 2>/dev/null || echo "⚠️ Warning: Failed to start Redis. Make sure Docker is running."

stop-redis:
	@echo "🛑 Stopping local Redis container..."
	@docker stop reco-redis 2>/dev/null || true

reset-redis:
	@echo "🔄 Resetting local Redis container..."
	@docker rm -f reco-redis 2>/dev/null || true
	@docker run -d --name reco-redis -p 6379:6379 redis:alpine

redis-cli:
	@echo "💬 Connecting to local Redis container..."
	@docker exec -it reco-redis redis-cli

start: check-gcloud-auth start-redis
	@trap '$(MAKE) stop-redis' EXIT INT TERM; \
	uv run src/main.py

show-config:
	@PYTHONPATH=src uv run python -c "from main import show_api_config; show_api_config()"

SSH_BASE = gcloud compute ssh --zone "$$GCP_ZONE" "$$GCP_IAP_BASTION_INSTANCE_NAME" --tunnel-through-iap --project "$$GCP_BASTION_PROJECT" --

define PREPARE_TUNNEL
	@source .env && \
	REQUIRED_VARS=("GCP_ZONE" "GCP_IAP_BASTION_INSTANCE_NAME" "GCP_BASTION_PROJECT" "SQL_PORT" "REMOTE_SQL_HOST" "REMOTE_SQL_PORT"); \
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

start-with-remote-db:
	$(PREPARE_TUNNEL)
	@echo "🔌 Establishing SSH tunnel in background..."
	@source .env && $(SSH_BASE) -N -q -L "$$SQL_PORT":"$$REMOTE_SQL_HOST":"$$REMOTE_SQL_PORT" & \
	TUNNEL_PID=$$! ; \
	sleep 2; \
	trap 'echo -e "\n🛑 Stopping API. Closing SSH tunnel (PID: $$TUNNEL_PID)..."; kill $$TUNNEL_PID 2>/dev/null || true' EXIT INT TERM ; \
	$(MAKE) start

streamlit: check-gcloud-auth
	uv run streamlit run streamlit/app.py


streamlit-remote: check-gcloud-auth
	$(PREPARE_SWAGGER_TUNNEL)
	@echo "🔌 Opening SOCKS tunnel in background for Streamlit$(if $(DEPLOY_ENV), [env: $(DEPLOY_ENV)],)..."
	@$(load_env_cmd) && \
	export REMOTE_API_URL REMOTE_API_V1_URL REMOTE_API_TOKEN REMOTE_API_SOCKS_PORT && \
	export STREAMLIT_DEFAULT_API_VERSION="$(VERSION)" && \
	SOCKS_PORT="$${REMOTE_API_SOCKS_PORT:-1080}" ; \
	$(SSH_BASE) -N -q -D "$$SOCKS_PORT" & \
	TUNNEL_PID=$$! ; \
	sleep 2; \
	trap 'echo -e "\n🛑 Closing SOCKS tunnel (PID: $$TUNNEL_PID)..."; kill $$TUNNEL_PID 2>/dev/null || true' EXIT INT TERM ; \
	echo "✅ Tunnel SOCKS ouvert sur le port $$SOCKS_PORT" ; \
	echo "👉 Dans le Streamlit, configurez le proxy : socks5://localhost:$$SOCKS_PORT" ; \
	$(MAKE) streamlit

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

unit-test:
	@echo "🧪 Running unit tests..."
	uv run pytest tests -m unit

integration-test:
	@docker info > /dev/null 2>&1 || (echo "❌ Error: Docker is not running. Please start Docker and try again."; exit 1)
	@echo "🧪 Running integration tests..."
	uv run pytest tests -m integration

test-with-markers:
	@echo "🧪 Verifying all tests are marked..."
	@TOTAL=$$(uv run pytest --collect-only -q | grep -c "test_"); \
	MARKED=$$(uv run pytest --collect-only -m "unit or integration" -q | grep -c "test_"); \
	if [ "$$TOTAL" -eq "$$MARKED" ]; then \
		echo "✓ All tests are marked (total: $$TOTAL)"; \
	else \
		echo "✗ Missing markers! Total: $$TOTAL, Marked: $$MARKED"; \
		exit 1; \
	fi

define PREPARE_SWAGGER_TUNNEL
	@$(load_env_cmd) && \
	REQUIRED_VARS=("GCP_ZONE" "GCP_IAP_BASTION_INSTANCE_NAME" "GCP_BASTION_PROJECT" "REMOTE_API_SOCKS_PORT" "REMOTE_API_URL"); \
	for var in "$${REQUIRED_VARS[@]}"; do \
	   if [ -z "$${!var}" ]; then echo "❌ Error: $$var is missing in .env$(if $(DEPLOY_ENV),.$(DEPLOY_ENV),)"; exit 1; fi; \
	done; \
	echo "🧹 Cleaning up port $$REMOTE_API_SOCKS_PORT..." && \
	lsof -ti:$$REMOTE_API_SOCKS_PORT | xargs kill -9 2>/dev/null || true
endef

UNAME_S := $(shell uname -s)

ifeq ($(UNAME_S),Linux)
    CHROME_BIN := google-chrome
else ifeq ($(UNAME_S),Darwin)
    CHROME_BIN := /Applications/Google Chrome.app/Contents/MacOS/Google Chrome
endif

VERSION ?= v2

access-remote-swagger: check-gcloud-auth
	$(PREPARE_SWAGGER_TUNNEL)
	@echo "🔌 Opening SOCKS tunnel to remote API$(if $(DEPLOY_ENV), [env: $(DEPLOY_ENV)],) [$(VERSION)]..."
	@$(load_env_cmd) && \
	SOCKS_PORT="$${REMOTE_API_SOCKS_PORT:-1080}" ; \
	if [ "$(VERSION)" = "v1" ] || [ "$(VERSION)" = "V1" ] || [ "$(VERSION)" = "1" ]; then \
		TARGET_URL="$$REMOTE_API_V1_URL" ; \
		if [ -z "$$TARGET_URL" ]; then echo "❌ Error: REMOTE_API_V1_URL is missing in .env$(if $(DEPLOY_ENV),.$(DEPLOY_ENV),)"; exit 1; fi ; \
	else \
		TARGET_URL="$$REMOTE_API_URL" ; \
	fi ; \
	$(SSH_BASE) -N -D "$$SOCKS_PORT" & \
	TUNNEL_PID=$$! ; \
	echo "⏳ Waiting for tunnel initialization..." ; \
	sleep 3 ; \
	echo "🔄 Tunnel might need more time. If the page fails to load, please refresh the window." ; \
	echo "🚀 Opening Google Chrome with SOCKS proxy on $$TARGET_URL/docs ..." ; \
	"$(CHROME_BIN)" \
		--proxy-server="socks5://localhost:$$SOCKS_PORT" \
		--user-data-dir="/tmp/chrome_proxy_tmp" \
		--no-first-run \
		--no-default-browser-check \
		"$$TARGET_URL/docs" \
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
