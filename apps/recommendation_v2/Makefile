SHELL:=/bin/bash

.PHONY: install start tunnel start-with-remote-db streamlit streamlit-remote dev-with-streamlit test unit-test integration-test test-with-markers access-remote-swagger get-api-token show-config load-test load-test-headless load-test-remote load-test-remote-headless load-test-benchmark locust-seed-data help


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
define resolve_api_url
	if [ "$(VERSION)" = "v1" ] || [ "$(VERSION)" = "V1" ] || [ "$(VERSION)" = "1" ]; then \
		TARGET_URL="$$REMOTE_API_V1_URL" ; \
		if [ -z "$$TARGET_URL" ]; then echo "❌ Error: REMOTE_API_V1_URL is missing in .env$(if $(DEPLOY_ENV),.$(DEPLOY_ENV),)"; exit 1; fi ; \
	else \
		TARGET_URL="$$REMOTE_API_URL" ; \
	fi ; \
	export STREAMLIT_DEFAULT_API_VERSION="$(VERSION)"
endef

# Resolve LOAD_TEST_TARGET_URL for load tests using dedicated Cloud Run instances.
#   v1          → LOAD_TEST_V1_URL
#   v2-no-redis → LOAD_TEST_V2_NO_REDIS_URL
#   v2 (default)→ LOAD_TEST_V2_REDIS_URL
define resolve_load_test_url
	if [ "$(VERSION)" = "v1" ] || [ "$(VERSION)" = "V1" ] || [ "$(VERSION)" = "1" ]; then \
		LOAD_TEST_TARGET_URL="$$LOAD_TEST_V1_URL" ; \
		if [ -z "$$LOAD_TEST_TARGET_URL" ]; then echo "❌ Error: LOAD_TEST_V1_URL is missing in .env$(if $(DEPLOY_ENV),.$(DEPLOY_ENV),)"; exit 1; fi ; \
	elif [ "$(VERSION)" = "v2-no-redis" ]; then \
		LOAD_TEST_TARGET_URL="$$LOAD_TEST_V2_NO_REDIS_URL" ; \
		if [ -z "$$LOAD_TEST_TARGET_URL" ]; then echo "❌ Error: LOAD_TEST_V2_NO_REDIS_URL is missing in .env$(if $(DEPLOY_ENV),.$(DEPLOY_ENV),)"; exit 1; fi ; \
	else \
		LOAD_TEST_TARGET_URL="$$LOAD_TEST_V2_REDIS_URL" ; \
		if [ -z "$$LOAD_TEST_TARGET_URL" ]; then echo "❌ Error: LOAD_TEST_V2_REDIS_URL is missing in .env$(if $(DEPLOY_ENV),.$(DEPLOY_ENV),)"; exit 1; fi ; \
	fi
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

get-api-token: check-gcloud-auth ## Fetch the API token from GCP Secret Manager. Requires DEPLOY_ENV=dev|stg|prod
	@[ -n "$(DEPLOY_ENV)" ] || (echo "❌ Error: DEPLOY_ENV is required. Usage: make get-api-token DEPLOY_ENV=dev|stg|prod"; exit 1)
	@$(load_env_cmd) && \
	if [ -z "$$GCP_SECRET_PROJECT" ] || [ -z "$$API_RECO_TOKEN_SECRET_NAME" ]; then \
		echo "❌ Error: GCP_SECRET_PROJECT or API_RECO_TOKEN_SECRET_NAME is missing from .env.$(DEPLOY_ENV)"; \
		exit 1; \
	fi; \
	echo "🔐 Fetching API token for [$(DEPLOY_ENV)]..." && \
	gcloud secrets versions access latest --secret "$$API_RECO_TOKEN_SECRET_NAME" --project "$$GCP_SECRET_PROJECT"


# ===========================================
# 🔥 Load tests (Locust)
# ===========================================

load-test: ## Start Locust UI against the local API (no proxy, no token required)
	@echo "🔥 Starting Locust UI against local API..."
	LOCUST_USE_SOCKS_PROXY=0 \
	uv run locust -f locust/locustfile.py

load-test-headless: ## Run Locust headless against the local API (shape-driven, ~5m30s, no proxy)
	@echo "🔥 Running headless Locust load test against local API..."
	LOCUST_USE_SOCKS_PROXY=0 \
	uv run locust -f locust/locustfile.py \
		--headless \
		--users 20 \
		--spawn-rate 2 \
		--html locust/reports/report_local_$$(date +%Y%m%d_%H%M%S).html

load-test-remote: check-gcloud-auth ## Start Locust UI against a remote load-test API via SOCKS tunnel. Requires DEPLOY_ENV=dev|stg|prod. Optional: VERSION=v1|v2|v2-no-redis TARGET_ENDPOINT=all|offers|playlist|artists
	@[ -n "$(DEPLOY_ENV)" ] || (echo "❌ Error: DEPLOY_ENV is required. Usage: make load-test-remote DEPLOY_ENV=dev|stg|prod"; exit 1)
	$(PREPARE_SWAGGER_TUNNEL)
	@echo "🔌 Opening SOCKS tunnel for Locust [env: $(DEPLOY_ENV)] [$(VERSION)] [endpoint: $(TARGET_ENDPOINT)]..."
	@$(load_env_cmd) && \
	SOCKS_PORT="$${REMOTE_API_SOCKS_PORT:-1080}" ; \
	$(resolve_load_test_url) ; \
	$(SSH_BASE) -N -q -D "$$SOCKS_PORT" & \
	TUNNEL_PID=$$! ; \
	sleep 2 ; \
	trap 'echo -e "\n🛑 Closing SOCKS tunnel (PID: $$TUNNEL_PID)..."; kill $$TUNNEL_PID 2>/dev/null || true' EXIT INT TERM ; \
	echo "✅ Tunnel SOCKS ouvert sur le port $$SOCKS_PORT" ; \
	echo "🔥 Starting Locust UI → http://localhost:8089  (target: $$LOAD_TEST_TARGET_URL, endpoint: $(TARGET_ENDPOINT))" ; \
	REMOTE_API_URL="$$LOAD_TEST_TARGET_URL" \
	REMOTE_API_TOKEN="$$REMOTE_API_TOKEN" \
	REMOTE_API_SOCKS_PORT="$$SOCKS_PORT" \
	LOCUST_USE_SOCKS_PROXY=1 \
	TARGET_ENDPOINT="$(TARGET_ENDPOINT)" \
	uv run locust -f locust/locustfile.py --host "$$LOAD_TEST_TARGET_URL"

load-test-remote-headless: check-gcloud-auth ## Run Locust headless against a remote load-test API via SOCKS tunnel (shape-driven, ~5m30s). Requires DEPLOY_ENV=dev|stg|prod. Optional: VERSION=v1|v2|v2-no-redis TARGET_ENDPOINT=all|offers|playlist|artists
	@[ -n "$(DEPLOY_ENV)" ] || (echo "❌ Error: DEPLOY_ENV is required. Usage: make load-test-remote-headless DEPLOY_ENV=dev|stg|prod"; exit 1)
	$(PREPARE_SWAGGER_TUNNEL)
	@echo "🔌 Opening SOCKS tunnel for headless Locust [env: $(DEPLOY_ENV)] [$(VERSION)] [endpoint: $(TARGET_ENDPOINT)]..."
	@$(load_env_cmd) && \
	SOCKS_PORT="$${REMOTE_API_SOCKS_PORT:-1080}" ; \
	$(resolve_load_test_url) ; \
	$(SSH_BASE) -N -q -D "$$SOCKS_PORT" & \
	TUNNEL_PID=$$! ; \
	sleep 2 ; \
	trap 'echo -e "\n🛑 Closing SOCKS tunnel (PID: $$TUNNEL_PID)..."; kill $$TUNNEL_PID 2>/dev/null || true' EXIT INT TERM ; \
	echo "🔥 Running headless Locust load test (shape-driven, ~5m30s)  (target: $$LOAD_TEST_TARGET_URL, endpoint: $(TARGET_ENDPOINT))" ; \
	REMOTE_API_URL="$$LOAD_TEST_TARGET_URL" \
	REMOTE_API_TOKEN="$$REMOTE_API_TOKEN" \
	REMOTE_API_SOCKS_PORT="$$SOCKS_PORT" \
	LOCUST_USE_SOCKS_PROXY=1 \
	TARGET_ENDPOINT="$(TARGET_ENDPOINT)" \
	uv run locust -f locust/locustfile.py \
		--host "$$LOAD_TEST_TARGET_URL" \
		--headless \
		--users 20 \
		--spawn-rate 2 \
		--html locust/reports/report_$(DEPLOY_ENV)_$(VERSION)_$$(date +%Y%m%d_%H%M%S).html ; \
	wait $$TUNNEL_PID

load-test-benchmark: check-gcloud-auth ## Run headless Locust benchmark (~5m30s) against v1, v2-redis and v2-no-redis in parallel. Requires DEPLOY_ENV=dev|stg|prod. Optional: TARGET_ENDPOINT=all(default)|offers|playlist|artists|"offers,playlist" (comma-separated → one sequential run per endpoint, ~5m30s each)
	@[ -n "$(DEPLOY_ENV)" ] || (echo "❌ Error: DEPLOY_ENV is required. Usage: make load-test-benchmark DEPLOY_ENV=dev|stg|prod"; exit 1)
	$(PREPARE_SWAGGER_TUNNEL)
	@echo "🔌 Opening SOCKS tunnel for benchmark [env: $(DEPLOY_ENV)] [endpoint: $(or $(TARGET_ENDPOINT),all)]..."
	@$(load_env_cmd) && \
	SOCKS_PORT="$${REMOTE_API_SOCKS_PORT:-1080}" ; \
	$(SSH_BASE) -N -q -D "$$SOCKS_PORT" & \
	TUNNEL_PID=$$! ; \
	sleep 2 ; \
	trap 'echo -e "\n🛑 Closing SOCKS tunnel (PID: $$TUNNEL_PID)..."; kill $$TUNNEL_PID 2>/dev/null || true' EXIT INT TERM ; \
	TIMESTAMP=$$(date +%Y%m%d_%H%M%S) ; \
	TARGET="$(TARGET_ENDPOINT)" ; \
	if [ -z "$$TARGET" ] || [ "$$TARGET" = "all" ]; then \
		RUN_MODE="benchmark" ; \
		REPORT_DIR="locust/reports/benchmark_$(DEPLOY_ENV)_$$TIMESTAMP" ; \
		echo "📊 Mode: benchmark complet (shape ~5m30s)" ; \
	else \
		RUN_MODE="isolated" ; \
		REPORT_DIR="locust/reports/isolated_$(DEPLOY_ENV)_$$TIMESTAMP" ; \
		echo "📊 Mode: isolated — endpoints: $$TARGET (2 min chacun)" ; \
	fi ; \
	mkdir -p "$$REPORT_DIR" ; \
	echo "📁 Reports will be saved in $$REPORT_DIR" ; \
	echo "" ; \
	PIDS="" ; \
	\
	run_version() { \
		local VER_LABEL=$$1 ; \
		local API_URL=$$2 ; \
		if [ "$$RUN_MODE" = "benchmark" ]; then \
			echo "🔥 Starting [$$VER_LABEL] → $$API_URL" ; \
			REMOTE_API_URL="$$API_URL" \
			REMOTE_API_TOKEN="$$REMOTE_API_TOKEN" \
			REMOTE_API_SOCKS_PORT="$$SOCKS_PORT" \
			LOCUST_USE_SOCKS_PROXY=1 \
			uv run locust -f locust/locustfile.py \
				--host "$$API_URL" \
				--headless \
				--users 20 \
				--spawn-rate 2 \
				--html "$$REPORT_DIR/report_$${VER_LABEL}.html" \
				> "$$REPORT_DIR/locust_$${VER_LABEL}.log" 2>&1 \
			&& echo "  ✅ [$$VER_LABEL] done" \
			|| echo "  ❌ [$$VER_LABEL] failed — check $$REPORT_DIR/locust_$${VER_LABEL}.log" ; \
		else \
			echo "🔥 [$$VER_LABEL] Starting isolated runs ($$TARGET) → $$API_URL" ; \
			IFS=',' read -ra ENDPOINT_LIST <<< "$$TARGET" ; \
			for ENDPOINT in "$${ENDPOINT_LIST[@]}"; do \
				ENDPOINT=$$(echo "$$ENDPOINT" | xargs) ; \
				REMOTE_API_URL="$$API_URL" \
				REMOTE_API_TOKEN="$$REMOTE_API_TOKEN" \
				REMOTE_API_SOCKS_PORT="$$SOCKS_PORT" \
				LOCUST_USE_SOCKS_PROXY=1 \
				TARGET_ENDPOINT="$$ENDPOINT" \
				uv run locust -f locust/locustfile.py \
					--host "$$API_URL" \
					--headless \
					--users 20 \
					--spawn-rate 2 \
					--html "$$REPORT_DIR/report_$${VER_LABEL}_$${ENDPOINT}.html" \
					>> "$$REPORT_DIR/locust_$${VER_LABEL}.log" 2>&1 \
				&& echo "  ✅ [$$VER_LABEL] $$ENDPOINT done" \
				|| echo "  ❌ [$$VER_LABEL] $$ENDPOINT failed — check $$REPORT_DIR/locust_$${VER_LABEL}.log" ; \
			done ; \
		fi ; \
	} ; \
	export -f run_version ; \
	export REMOTE_API_TOKEN SOCKS_PORT REPORT_DIR RUN_MODE TARGET ; \
	\
	if [ -n "$$LOAD_TEST_V1_URL" ]; then \
		( run_version "v1" "$$LOAD_TEST_V1_URL" ) & \
		PIDS="$$PIDS $$!" ; \
	else \
		echo "⚠️  Skipping v1 : LOAD_TEST_V1_URL not defined in .env.$(DEPLOY_ENV)" ; \
	fi ; \
	\
	if [ -n "$$LOAD_TEST_V2_REDIS_URL" ]; then \
		( run_version "v2-redis" "$$LOAD_TEST_V2_REDIS_URL" ) & \
		PIDS="$$PIDS $$!" ; \
	else \
		echo "⚠️  Skipping v2-redis : LOAD_TEST_V2_REDIS_URL not defined in .env.$(DEPLOY_ENV)" ; \
	fi ; \
	\
	if [ -n "$$LOAD_TEST_V2_NO_REDIS_URL" ]; then \
		( run_version "v2-no-redis" "$$LOAD_TEST_V2_NO_REDIS_URL" ) & \
		PIDS="$$PIDS $$!" ; \
	else \
		echo "⚠️  Skipping v2-no-redis : LOAD_TEST_V2_NO_REDIS_URL not defined in .env.$(DEPLOY_ENV)" ; \
	fi ; \
	\
	if [ -z "$$PIDS" ]; then \
		echo "❌ No load-test URLs defined — nothing to run." ; \
		kill $$TUNNEL_PID 2>/dev/null || true ; \
		exit 1 ; \
	fi ; \
	echo "⏳ All versions running in parallel, waiting for completion…" ; \
	FAILED=0 ; \
	for PID in $$PIDS; do \
		wait $$PID || FAILED=$$((FAILED + 1)) ; \
	done ; \
	echo "" ; \
	echo "🏁 Benchmark complete! Reports:" ; \
	ls -1 "$$REPORT_DIR"/*.html 2>/dev/null | sed 's/^/  📄 /' ; \
	echo "📋 Logs:" ; \
	ls -1 "$$REPORT_DIR"/*.log 2>/dev/null | sed 's/^/  📝 /' ; \
	[ "$$FAILED" -eq 0 ] || echo "⚠️  $$FAILED version(s) had errors — check the logs above." ; \
	kill $$TUNNEL_PID 2>/dev/null || true


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

all-tests-marked: ## Verify that every test has a unit or integration marker
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
