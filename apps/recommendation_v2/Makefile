SHELL:=/bin/bash

.PHONY: install start tunnel start-with-remote-db streamlit streamlit-remote dev-with-streamlit test unit-test integration-test test-with-markers access-remote-swagger get-staging-api-token show-config help


# ===========================================
# 📦 Setup
# ===========================================

install: ## Install dependencies and create virtual environment
	@echo "📦 Installing dependencies..."
	UV_VENV_CLEAR=1 uv venv && uv sync --locked

check-gcloud-auth: ## Check and refresh gcloud CLI and ADC authentication
	@echo "🔍 Checking gcloud CLI authentication..."
	@gcloud auth print-access-token > /dev/null 2>&1 || (echo "🔐 CLI not authenticated. Launching gcloud auth login..." && gcloud auth login)
	@echo "🔍 Checking Application Default Credentials (ADC) for Python SDKs..."
	@gcloud auth application-default print-access-token > /dev/null 2>&1 || (echo "🔐 ADC not authenticated. Launching gcloud application-default login..." && gcloud auth application-default login)


# ===========================================
# 🚀 Local API
# ===========================================

# SSH base command used to connect to the GCP bastion via IAP
SSH_BASE = gcloud compute ssh --zone "$$GCP_ZONE" "$$GCP_IAP_BASTION_INSTANCE_NAME" --tunnel-through-iap --project "$$GCP_BASTION_PROJECT" --

# Validate required vars and free the DB tunnel port before opening a new tunnel
define PREPARE_TUNNEL
	@source .env && \
	REQUIRED_VARS=("GCP_ZONE" "GCP_IAP_BASTION_INSTANCE_NAME" "GCP_BASTION_PROJECT" "SQL_PORT" "REMOTE_SQL_HOST" "REMOTE_SQL_PORT"); \
	for var in "$${REQUIRED_VARS[@]}"; do \
	   if [ -z "$${!var}" ]; then echo "❌ Error: $$var is missing in .env"; exit 1; fi; \
	done; \
	echo "🧹 Cleaning up port $$SQL_PORT..." && \
	lsof -ti:$$SQL_PORT | xargs kill -9 2>/dev/null || true
endef

start: check-gcloud-auth start-redis ## Start the API locally (starts Redis automatically)
	@trap '$(MAKE) stop-redis' EXIT INT TERM; \
	uv run src/main.py

show-config: ## Print the resolved API configuration (env vars as seen by the app)
	@PYTHONPATH=src uv run python -c "from main import show_api_config; show_api_config()"

start-with-remote-db: ## Start the API with an SSH tunnel to the remote DB
	$(PREPARE_TUNNEL)
	@echo "🔌 Establishing SSH tunnel in background..."
	@source .env && $(SSH_BASE) -N -q -L "$$SQL_PORT":"$$REMOTE_SQL_HOST":"$$REMOTE_SQL_PORT" & \
	TUNNEL_PID=$$! ; \
	sleep 2; \
	trap 'echo -e "\n🛑 Stopping API. Closing SSH tunnel (PID: $$TUNNEL_PID)..."; kill $$TUNNEL_PID 2>/dev/null || true' EXIT INT TERM ; \
	$(MAKE) start

tunnel: check-gcloud-auth ## Open a standalone SSH tunnel to the remote DB (foreground)
	$(PREPARE_TUNNEL)
	@echo "🔌 Opening standalone SSH tunnel..."
	@source .env && $(SSH_BASE) -L "$$SQL_PORT":"$$REMOTE_SQL_HOST":"$$REMOTE_SQL_PORT"


# ===========================================
# 🗄️ Redis
# ===========================================

start-redis: ## Start the local Redis container (creates it if it does not exist)
	@echo "🚀 Starting local Redis container..."
	@docker start reco-redis 2>/dev/null || docker run -d --name reco-redis -p 6379:6379 redis:alpine 2>/dev/null || echo "⚠️ Warning: Failed to start Redis. Make sure Docker is running."

stop-redis: ## Stop the local Redis container
	@echo "🛑 Stopping local Redis container..."
	@docker stop reco-redis 2>/dev/null || true

reset-redis: ## Destroy and recreate the local Redis container (clears all cached data)
	@echo "🔄 Resetting local Redis container..."
	@docker rm -f reco-redis 2>/dev/null || true
	@docker run -d --name reco-redis -p 6379:6379 redis:alpine

redis-cli: ## Open an interactive Redis CLI session inside the local container
	@echo "💬 Connecting to local Redis container..."
	@docker exec -it reco-redis redis-cli


# ===========================================
# 🎨 Streamlit UI
# ===========================================

# Load .env then optionally override with .env.<DEPLOY_ENV>
# Usage: make <target> DEPLOY_ENV=dev|stg|prod
# NOTE: we use DEPLOY_ENV (not ENV) to avoid collision with the app's ENV variable (used by settings.py)
DEPLOY_ENV ?=
define load_env_cmd
	source .env $(if $(DEPLOY_ENV),&& [ -f .env.$(DEPLOY_ENV) ] && source .env.$(DEPLOY_ENV) || true,)
endef

# Validate required vars and free the SOCKS port before opening a new tunnel
define PREPARE_SWAGGER_TUNNEL
	@$(load_env_cmd) && \
	REQUIRED_VARS=("GCP_ZONE" "GCP_IAP_BASTION_INSTANCE_NAME" "GCP_BASTION_PROJECT" "REMOTE_API_SOCKS_PORT" "REMOTE_API_URL"); \
	for var in "$${REQUIRED_VARS[@]}"; do \
	   if [ -z "$${!var}" ]; then echo "❌ Error: $$var is missing in .env$(if $(DEPLOY_ENV),.$(DEPLOY_ENV),)"; exit 1; fi; \
	done; \
	echo "🧹 Cleaning up port $$REMOTE_API_SOCKS_PORT..." && \
	lsof -ti:$$REMOTE_API_SOCKS_PORT | xargs kill -9 2>/dev/null || true
endef

streamlit: check-gcloud-auth ## Start the Streamlit UI locally (against the local API)
	uv run streamlit run streamlit/app.py

dev-with-streamlit: check-gcloud-auth ## Start API + Streamlit UI with SSH tunnel to remote DB
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

streamlit-remote: check-gcloud-auth ## Start Streamlit UI against a remote API via SOCKS tunnel. Requires DEPLOY_ENV=dev|stg|prod
	@[ -n "$(DEPLOY_ENV)" ] || (echo "❌ Error: DEPLOY_ENV is required. Usage: make streamlit-remote DEPLOY_ENV=dev|stg|prod"; exit 1)
	$(PREPARE_SWAGGER_TUNNEL)
	@echo "🔌 Opening SOCKS tunnel in background for Streamlit$(if $(DEPLOY_ENV), [env: $(DEPLOY_ENV)],)..."
	@$(load_env_cmd) && \
	SOCKS_PORT="$${REMOTE_API_SOCKS_PORT:-1080}" ; \
	$(SSH_BASE) -N -q -D "$$SOCKS_PORT" & \
	TUNNEL_PID=$$! ; \
	sleep 2; \
	trap 'echo -e "\n🛑 Closing SOCKS tunnel (PID: $$TUNNEL_PID)..."; kill $$TUNNEL_PID 2>/dev/null || true' EXIT INT TERM ; \
	echo "✅ Tunnel SOCKS ouvert sur le port $$SOCKS_PORT" ; \
	echo "👉 Dans le Streamlit, configurez le proxy : socks5://localhost:$$SOCKS_PORT" ; \
	REMOTE_API_URL="$$REMOTE_API_URL" \
	REMOTE_API_V1_URL="$$REMOTE_API_V1_URL" \
	REMOTE_API_TOKEN="$$REMOTE_API_TOKEN" \
	REMOTE_API_SOCKS_PORT="$$REMOTE_API_SOCKS_PORT" \
	uv run --no-env-file streamlit run streamlit/app.py


# ===========================================
# 🔌 Remote access (requires DEPLOY_ENV=dev|stg|prod)
# ===========================================

# Resolve TARGET_URL based on VERSION (v1 → REMOTE_API_V1_URL, else → REMOTE_API_URL)
# Usage: call inside a shell block after load_env_cmd
VERSION ?= v2
define resolve_api_url
	if [ "$(VERSION)" = "v1" ] || [ "$(VERSION)" = "V1" ] || [ "$(VERSION)" = "1" ]; then \
		TARGET_URL="$$REMOTE_API_V1_URL" ; \
		if [ -z "$$TARGET_URL" ]; then echo "❌ Error: REMOTE_API_V1_URL is missing in .env$(if $(DEPLOY_ENV),.$(DEPLOY_ENV),)"; exit 1; fi ; \
	else \
		TARGET_URL="$$REMOTE_API_URL" ; \
	fi ; \
	export STREAMLIT_DEFAULT_API_VERSION="$(VERSION)"
endef

UNAME_S := $(shell uname -s)
ifeq ($(UNAME_S),Linux)
    CHROME_BIN := google-chrome
else ifeq ($(UNAME_S),Darwin)
    CHROME_BIN := /Applications/Google Chrome.app/Contents/MacOS/Google Chrome
endif

access-remote-swagger: check-gcloud-auth ## Open remote Swagger UI in Chrome via SOCKS tunnel. Requires DEPLOY_ENV=dev|stg|prod. Optional: VERSION=v1
	@[ -n "$(DEPLOY_ENV)" ] || (echo "❌ Error: DEPLOY_ENV is required. Usage: make access-remote-swagger DEPLOY_ENV=dev|stg|prod"; exit 1)
	$(PREPARE_SWAGGER_TUNNEL)
	@echo "🔌 Opening SOCKS tunnel to remote API$(if $(DEPLOY_ENV), [env: $(DEPLOY_ENV)],) [$(VERSION)]..."
	@$(load_env_cmd) && \
	SOCKS_PORT="$${REMOTE_API_SOCKS_PORT:-1080}" ; \
	$(resolve_api_url) ; \
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

get-staging-api-token: check-gcloud-auth ## Fetch the API token from GCP Secret Manager
	@source .env && \
	if [ -z "$$GCP_SECRET_PROJECT" ] || [ -z "$$API_RECO_TOKEN_SECRET_NAME" ]; then \
		echo "❌ Error: GCP_SECRET_PROJECT or API_RECO_TOKEN_SECRET_NAME is missing from .env"; \
		exit 1; \
	fi; \
	echo "🔐 Fetching API token..." && \
	gcloud secrets versions access latest --secret "$$API_RECO_TOKEN_SECRET_NAME" --project "$$GCP_SECRET_PROJECT"


# ===========================================
# 🧪 Tests
# ===========================================

test: ## Run all tests
	@echo "🧪 Running unit tests..."
	uv run pytest tests

unit-test: ## Run unit tests only (no Docker required)
	@echo "🧪 Running unit tests..."
	uv run pytest tests -m unit

integration-test: ## Run integration tests only (requires Docker)
	@docker info > /dev/null 2>&1 || (echo "❌ Error: Docker is not running. Please start Docker and try again."; exit 1)
	@echo "🧪 Running integration tests..."
	uv run pytest tests -m integration

test-with-markers: ## Verify that every test has a unit or integration marker
	@echo "🧪 Verifying all tests are marked..."
	@TOTAL=$$(uv run pytest --collect-only -q | grep -c "test_"); \
	MARKED=$$(uv run pytest --collect-only -m "unit or integration" -q | grep -c "test_"); \
	if [ "$$TOTAL" -eq "$$MARKED" ]; then \
		echo "✓ All tests are marked (total: $$TOTAL)"; \
	else \
		echo "✗ Missing markers! Total: $$TOTAL, Marked: $$MARKED"; \
		exit 1; \
	fi


# ===========================================
# ℹ️  Help
# ===========================================

help: ## List all available commands with their description
	@echo ""
	@echo "Usage: make <command> [VARIABLE=value]"
	@echo ""
	@grep -E '^[a-zA-Z_-]+:.*## ' $(MAKEFILE_LIST) \
		| awk 'BEGIN {FS = ":.*## "}; {printf "  \033[36m%-30s\033[0m %s\n", $$1, $$2}'
	@echo ""
