# Data Recommendation API V2

Recommendation API V2 built with **FastAPI**, **PostgreSQL/PostGIS**, and **Google Cloud Vertex AI**.

This service acts as the core recommendation engine for the pass Culture platform, responsible for generating highly personalized, geo-localized, and diverse cultural playlists for our users.

## 📖 API Documentation

Once the server is running, interactive API documentation is available at:
👉 `<uri-api>/docs` (Swagger UI)

---

## 🚨 Coding Standards & Best Practices

Before writing any code or submitting a Pull Request, it is mandatory to read and follow our development standards.
👉 **[Read the API V2 Development Best Practices Guide on Notion](https://www.notion.so/passcultureapp/Qu-elles-sont-les-regles-a-respecter-pour-developper-l-API-de-recommendation-2eaad4e0ff988090b54df96129776d9e?source=copy_link)**

Ensure your code complies with our quality standards. While pre-commit hooks will format your code automatically when you commit, you can (and should) run these checks manually during development:

```bash
# Auto-fix linting and formatting issues
ruff check --fix

# Run strict type checking on the source code
ty check src
```

---

## 🏗️ How it Works: The Recommendation Pipeline

The V2 API operates as a recommendation funnel. It takes millions of potential cultural offers and progressively filters, resolves, scores, and mixes them to return a tailored playlist of up to 60 personalized items.

To drastically decrease repetitive computations and speed up subsequent identical user queries, the API utilizes a **Redis** caching layer that intercepts identical requests, returning the exact playlist directly without hitting the Vertex endpoints again.

Here is the step-by-step lifecycle of a single request:

### 0. ⚡ Cache Interception (`connectors/redis_api.py`)
* **The Goal:** Provide instant responses for identical repeated queries while ensuring data freshness.
* **Process:** If enabled, the API generates a unique MD5 signature. To increase hit rates and handle GPS precision jitter, the exact coordinates are normalized into an **H3 index (resolution 5)**. This signature also includes the user ID and query parameters.
* **Call ID Management:** If a result is returned from cache, a new unique `call_id` is automatically generated and injected into the response. This ensures that every recommendation display remains uniquely identifiable for downstream model retraining, even if the underlying list of offers was cached.
* **Expiration:** Cached data is dynamically set to expire based on the upcoming database reset cycle (`REDIS_CACHE_RESET_HOUR`).

### 1. 👤 Contextualization (`core/user_context.py`, `core/geo.py`)
* **The Goal:** Build a snapshot of the user's state at request time.
* **Process:** Retrieves the user's interaction history (bookings, clicks) and uses PostGIS spatial intersection to find their geographical zone (French 'IRIS'). This stage critically determines if the user is in a "Cold Start" state.

### 2. 🔍 Candidate Retrieval (`core/retrieval.py` -> Vertex AI)
* **The Goal:** Cast a wide net to fetch up to 150 relevant candidate items.
* **Process:** Incoming HTTP parameters (price limits, dates, categories) are translated into vector-search constraints. The primary Vertex AI model is then called to fetch raw items based on the user's profile and these filters.

### 3. 📍 Spatial Resolution (`core/retrieval.py` -> PostgreSQL/PostGIS)
* **The Goal:** Convert abstract ML items (e.g., "The Matrix Movie") into concrete, real-world offers (e.g., "Screening at 8 PM, 2km away").
* **Process:** Digital items are resolved directly in code. Physical items are routed to a PostGIS database query that uses window functions (`ST_Distance`) to retain only the single closest venue for each item.

### 4. 🥇 ML Ranking (`core/ranking.py` -> Vertex AI)
* **The Goal:** Score and re-order the resolved physical and digital offers.
* **Process:** A secondary Vertex AI Ranking model evaluates a dense feature vector (time of day, exact distance, remaining user credit, etc.) to predict the highest probability of engagement and sorts the playlist accordingly.

### 5. 🔀 Diversification (`core/diversification.py`)
* **The Goal:** Prevent "category fatigue" by ensuring a healthy mix of cultural domains (e.g., mixing manga, cinema, and museum tickets).
* **Process:** Offers are grouped by category. A prioritized Round-Robin interleaving algorithm shuffles these domains while respecting the initial ML ranking scores.

### 6. 📈 Telemetry & Feedback Loop (`core/tracking.py` -> GCP Sink)
* **The Goal:** Record the exact context of the recommendation for future model training.
* **Process:** The final playlist and user context are logged as a structured JSON payload. A GCP Sink intercepts this specific log and streams it into BigQuery, serving as the Ground Truth for the Data Science team.

---

## 📂 Folder Structure

```text
src/
├── api/              # FastAPI Routes (HTTP Controllers)
├── config/           # Centralized configuration & Environment variables
├── connectors/       # Adapters bridging core logic and external services (e.g., VertexAPI, Redis)
├── core/             # Core recommendation engine logic
│   ├── pipeline.py         # 1. Main orchestrator tying all steps together
│   ├── user_context.py     # 2. User state management & ML feature engineering
│   ├── geo.py              # 3. PostGIS spatial queries for user location
│   ├── retrieval.py        # 4. Candidate fetching & Spatial routing
│   ├── ranking.py          # 5. Scoring via Vertex Ranking
│   ├── diversification.py  # 6. Business rules & Round-Robin mixing
│   └── tracking.py         # 7. GCP Logging for BigQuery ingestion
├── models/           # SQLAlchemy database models (PostGIS/DB schema)
├── schemas/          # Pydantic models (Input/Output strict validation)
├── services/         # External infrastructure clients (Vertex, DB, Redis, H3, Logger)
└── streamlit/        # Streamlit UI acting as a visual proxy for the API

tests/
├── api/              # Route integration tests
└── conftest.py       # Pytest common fixtures
```

---

## 🛠️ How to DEV (Local Environment)

### 1. Prerequisites
We use `uv`, an ultra-fast tool for managing Python versions and virtual environments:
```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
```

### 2. Environment Setup

Configuration is split across two types of files:

| File | Purpose |
|------|---------|
| `.env` | Base configuration for the application (DB, GCP, Redis, logging, etc.) |
| `.env.<env>` | Environment-specific overrides for remote access (dev, stg, prod) |

Start by creating your base configuration file:
```bash
cp .env.template .env
# Fill in the missing values
```

If you need to connect to a remote environment (staging, prod), also create the corresponding override file:
```bash
cp .env.remote.template .env.stg   # or .env.dev / .env.prod
# Fill in the remote API URLs, token, and SSH tunnel configuration
```

The `.env.<env>` file is automatically loaded on top of `.env` when you pass `DEPLOY_ENV=<env>` to any Makefile command. Variables defined in `.env.<env>` take precedence over those in `.env`.

### 3. Google Cloud Authentication
To make local calls to the Vertex AI recommendation endpoints, you must authenticate your local machine with Google Cloud:
```bash
gcloud auth application-default login
```
*💡 Note: To ensure your local behavior is ISO with production during development, prioritize using the **PROD Vertex AI models** in your `.env` file.*

### 4. Install Dependencies
```bash
make install
```

### 5. Start Redis (Development / Cache Testing)
If you wish to test or use the cache mechanism during local development, ensure Redis is running via Docker (the `Makefile` automates it when standard API targets are launched, or you can manage it directly):
```bash
make start-redis
```
*💡 Note: To actually use the cache in the API, you must also set `REDIS_CACHE_ENABLED=1` in your `.env` file.*

*(You can interact directly with the cache store via `make redis-cli` or flush it via `make reset-redis`)*

### 6. Run the API (with Staging Database)
To develop and test locally using the Staging database, we use an automated SSH tunnel. You have two options depending on your needs:

#### **Option A: API Only**
Use this if you only need the backend running for local development or testing via external tools (like Postman or cURL).
```bash
make start-with-remote-db
```

#### **Option B: API + Streamlit Proxy UI (Recommended for Testing)**
This is the best way to visually inspect results, configure filters, and simulate user states (e.g., active or cold start) through a dedicated interface.
```bash
make dev-with-streamlit
```
* **Access:** Navigate to the local URL provided by Streamlit in your terminal.
* **Exit:** Press `Ctrl+C` to gracefully shut down the UI, API, and SSH tunnel simultaneously.

#### 💡 Troubleshooting & Notes
* **Manual SSH Setup:** If the tunnel fails to establish, check your `.env` variables or follow the **[Notion guide for manual SSH setup](https://www.notion.so/passcultureapp/Communiquer-avec-la-base-de-donn-es-de-l-API-Recommendation-Staging-via-sa-machine-locale-2fead4e0ff98808989e9d02d45394904?source=copy_link)**.
* **Local DB:** If you are running a fully local database instance (bypassing the tunnel), simply run `make start`.

### 7. Run Tests
```bash
make test           # all tests
make unit-test      # unit tests only
make integration-test  # integration tests only (requires Docker)
```

---

## 🔌 Accessing Remote Environments

Two dedicated Makefile commands allow you to connect to and inspect remote APIs (dev, staging, prod). Both require:
1. A `.env.<env>` file with the remote API configuration (see `.env.remote.template`).
2. `gcloud` to be authenticated (`make check-gcloud-auth`).
3. The `DEPLOY_ENV` variable to be explicitly passed — both commands **refuse to run without it**.

### Streamlit UI against a remote API

Launches a local Streamlit instance connected to a remote API through a SOCKS5 tunnel. The Streamlit sidebar lets you switch between API v1 and v2, configure a proxy, and inspect each request in detail.

```bash
make streamlit-remote DEPLOY_ENV=stg
# or
make streamlit-remote DEPLOY_ENV=prod
```

Once started:
- Open the Streamlit URL in your browser (default: `http://localhost:8501`)
- In the sidebar, set the **Proxy SOCKS5** field to: `socks5h://localhost:1080`
- The environment banner at the top of the page confirms which API you are targeting

### Access remote Swagger UI

Opens the Swagger `/docs` of a remote API directly in Google Chrome, routed through a SOCKS5 tunnel. Supports selecting API version v1 or v2.

```bash
make access-remote-swagger DEPLOY_ENV=stg           # opens v2 Swagger (default)
make access-remote-swagger DEPLOY_ENV=stg VERSION=v1  # opens v1 Swagger
```

### Get a remote API token

Fetches a valid API token from Google Secret Manager for the specified environment. Useful to authorize requests in the Swagger UI or Streamlit.

```bash
make get-api-token DEPLOY_ENV=stg
make get-api-token DEPLOY_ENV=prod
```

*Requires `GCP_SECRET_PROJECT` and `API_RECO_TOKEN_SECRET_NAME` to be set in the corresponding `.env.<env>` file.*

---

## 🔥 Load Tests (Locust)

Load tests are located in the `locust/` directory and use [Locust](https://locust.io/) to simulate realistic API traffic.

### Load shape

All test modes use the same `StagingLoadShape`, which simulates a realistic intra-day traffic profile:

```
Users
 20 |          ┌──────────┐
    |         /            \
  6 |────────/              \────────┐
    |  ramp  |  steady      |  ramp  |  steady  |  drain
    └──────────────────────────────────────────────────→ time
       30s      120s    150s  210s  240s   300s    330s
```

| Phase | Duration | Users | Throughput |
|---|---|---|---|
| 0 - Warm-up | 0 → 30s | 0 → 6 | ramp to ~6 req/s |
| 1 - Steady | 30s → 2min | 6 | ~6 req/s |
| 2 - Ramp to peak | 2min → 2min30 | 6 → 20 | ramp to ~20 req/s |
| 3 - Peak hold | 2min30 → 3min30 | 20 | ~20 req/s |
| 4 - Cool-down | 3min30 → 4min | 20 → 6 | ramp down |
| 5 - Steady | 4min → 5min | 6 | ~6 req/s |
| 6 - Drain | 5min → 5min30 | 6 → 0 | drain |

**Total duration ≈ 5 min 30 s.**

---

### Prerequisites: seed the test data

Before running any test, populate the `locust/data/` files with real IDs from the staging database. This requires the DB tunnel to be open first:

```bash
make tunnel DEPLOY_ENV=stg        # open the DB tunnel in a separate terminal
make locust-seed-data             # populate locust/data/ with real offer/user/artist IDs
```

The seed files (`sample_offer_ids.txt`, `sample_user_ids.txt`, `sample_artist_ids.txt`) are git-ignored.

---

### Deploy the load test Cloud Run instances

Remote load tests target **dedicated Cloud Run revisions** that are completely isolated from production traffic (0 % routing, max 1 instance). They are deployed via the **"Deploy Load Test Instances"** GitHub Actions workflow (manual trigger only).

#### Instances deployed

| Cloud Run tag | API version | Redis |
|---|---|---|
| `load-test-v1` | Reco v1 | N/A |
| `load-test-v2` | Reco v2 | ✅ enabled (`REDIS_CACHE_ENABLED=1`) |
| `load-test-v2-no-redis` | Reco v2 | ❌ disabled (`REDIS_CACHE_ENABLED=0`) |

> Both v2 variants share the same Docker image. Redis is toggled exclusively via the `REDIS_CACHE_ENABLED` environment variable at deploy time — no separate build is needed.

#### How to deploy

1. Go to **Actions → Deploy Load Test Instances** in GitHub.
2. Click **Run workflow** and fill in the inputs:
   - **environment**: `dev` or `staging`
   - Three checkboxes to select which instances to (re)deploy
3. Wait for the workflow to complete. The printed URL for each revision follows the pattern:
   ```
   https://load-test-v1---<base-service-url>
   https://load-test-v2---<base-service-url>
   https://load-test-v2-no-redis---<base-service-url>
   ```

#### Configure the URLs locally

Once deployed, copy the three tagged URLs into your `.env.<env>` file:

```bash
LOAD_TEST_V1_URL=https://load-test-v1---<base-service-url>
LOAD_TEST_V2_REDIS_URL=https://load-test-v2---<base-service-url>
LOAD_TEST_V2_NO_REDIS_URL=https://load-test-v2-no-redis---<base-service-url>
```

These variables are read by `make load-test-benchmark` and `make load-test-remote`.

---

### Local load tests

Run against a local API instance (no proxy, no token required).

```bash
make load-test            # interactive Locust UI at http://localhost:8089
make load-test-headless   # headless run (~5m30s), saves an HTML report in locust/reports/
```

---

### Remote load tests (single version)

Run against a dedicated load-test Cloud Run instance via a SOCKS5 IAP tunnel. Requires:
- `DEPLOY_ENV=dev|stg`
- A `.env.<env>` file with `LOAD_TEST_V1_URL` / `LOAD_TEST_V2_REDIS_URL` / `LOAD_TEST_V2_NO_REDIS_URL`, `REMOTE_API_TOKEN`, `REMOTE_API_SOCKS_PORT`
- The load-test instances deployed (see section above)

```bash
# Interactive UI — pick the version and endpoint to test
make load-test-remote DEPLOY_ENV=stg
make load-test-remote DEPLOY_ENV=stg VERSION=v1
make load-test-remote DEPLOY_ENV=stg TARGET_ENDPOINT=playlist

# Headless run (~5m30s) — saves an HTML report in locust/reports/
make load-test-remote-headless DEPLOY_ENV=stg
make load-test-remote-headless DEPLOY_ENV=stg VERSION=v2-no-redis TARGET_ENDPOINT=offers
```

**Optional parameters:**

| Parameter | Values | Default | Description |
|---|---|---|---|
| `VERSION` | `v1`, `v2`, `v2-no-redis` | `v2` | Selects the dedicated load-test Cloud Run instance |
| `TARGET_ENDPOINT` | `all`, `offers`, `playlist`, `artists` | `all` | Restricts load to a single endpoint |

---

### Benchmark (all versions in parallel)

Runs the full load shape against **v1, v2-redis, and v2-no-redis simultaneously** and saves one HTML report per version. Requires the load-test Cloud Run URLs (`LOAD_TEST_V1_URL`, `LOAD_TEST_V2_REDIS_URL`, `LOAD_TEST_V2_NO_REDIS_URL`) to be set in the `.env.<env>` file.

```bash
# Full benchmark — one report per version
make load-test-benchmark DEPLOY_ENV=stg

# Isolated mode — one report per version × per endpoint (runs sequentially per version)
make load-test-benchmark DEPLOY_ENV=stg TARGET_ENDPOINT=offers
make load-test-benchmark DEPLOY_ENV=stg TARGET_ENDPOINT=offers,playlist,artists
```

Reports are saved in `locust/reports/`:
- `benchmark_<env>_<timestamp>/` for full runs
- `isolated_<env>_<timestamp>/` for isolated endpoint runs

Each directory contains one `.html` report and one `.log` file per version.

---

### Base configuration (`.env`)

Copy `.env.template` to `.env` and fill in the values.
**Note:** For security reasons, sensitive values (IPs, passwords, project IDs) are not committed. Ask the Data Science team for the correct values or check the internal documentation.

#### 🌐 API Server
| Variable | Description |
|----------|-------------|
| `FASTAPI_SERVER_PORT` | The local port where the FastAPI server will run (e.g., `8801`). |

#### 🗄️ Database Connection
Used to connect to the PostgreSQL database. When running locally with `make start-with-remote-db`, these should point to the **local end of the SSH tunnel**.

| Variable | Description |
|----------|-------------|
| `SQL_HOST` | Hostname of the DB. Usually `127.0.0.1` when using the tunnel. |
| `SQL_PORT` | Local port forwarded to the remote DB. |
| `SQL_BASE` | Name of the database. |
| `SQL_BASE_USER` | Database username. |
| `SQL_BASE_PASSWORD` | Database password. |

#### 🧠 Google Cloud & Vertex AI
| Variable | Description |
|----------|-------------|
| `GCP_PROJECT` | GCP Project ID where the Vertex AI endpoints are hosted. |
| `VERTEX_RETRIEVAL_ENDPOINT_NAME` | Name of the Vertex AI Endpoint for the Retrieval model. |
| `VERTEX_RANKING_ENDPOINT_NAME` | Name of the Vertex AI Endpoint for the Ranking model. |
| `VERTEX_GRAPH_ENDPOINT_NAME` | Name of the Vertex AI Endpoint for the Graph model. |

#### 🏗️ Infrastructure & SSH Tunnels
Used by the Makefile to establish secure tunnels to the VPC (for DB access).

| Variable | Description |
|----------|-------------|
| `GCP_ZONE` | GCP Zone where the Bastion VM is located. |
| `GCP_IAP_BASTION_INSTANCE_NAME` | Name of the Bastion VM used for the DB tunnel. |
| `GCP_BASTION_PROJECT` | GCP Project ID where the Bastion VM is hosted. |
| `REMOTE_SQL_HOST` | Internal Private IP of the Cloud SQL instance. |
| `REMOTE_SQL_PORT` | Port of the remote Postgres instance (e.g., `5432`). |

#### 🗄️ Redis Caching Layer
| Variable | Description |
|----------|-------------|
| `REDIS_CACHE_ENABLED` | Set to `1` to enable Redis caching, `0` to disable. Default: `0` locally. |
| `REDIS_URL` | Connection string to the Redis server (e.g., `redis://localhost:6379/0`). |
| `REDIS_CACHE_RESET_HOUR` | The hour [0-23] at which the cache automatically expires (usually `5` AM). |

#### 🛠️ Debugging & Logs
| Variable | Description |
|----------|-------------|
| `LOGS_PRETTY_PRINT` | Set to `1` to enable colored, human-readable JSON logs for local dev. |
| `ENABLE_TRACKING_LOGS` | Set to `0` to disable sending tracking events to BigQuery during dev. |
| `SWAGGER_UI_EXAMPLE_USER_ID` | A valid User ID to pre-fill in the Swagger UI for testing. |
| `SWAGGER_UI_EXAMPLE_OFFER_ID` | A valid Offer ID to pre-fill in the Swagger UI for testing. |
| `SWAGGER_UI_EXAMPLE_OFFER_NAME` | A valid Offer name to pre-fill in the Swagger UI for testing. |

---

### Remote environment configuration (`.env.<env>`)

Copy `.env.remote.template` to `.env.dev`, `.env.stg`, or `.env.prod` and fill in the values.
These variables override the base `.env` when `DEPLOY_ENV=<env>` is passed to a Makefile command.

| Variable | Description |
|----------|-------------|
| `REMOTE_API_URL` | URL of the remote v2 API (used by `streamlit-remote` and `access-remote-swagger`). |
| `REMOTE_API_V1_URL` | URL of the remote v1 API (optional, enables the v1/v2 version selector in Streamlit). |
| `REMOTE_API_TOKEN` | API authentication token, pre-filled in the Streamlit sidebar. |
| `REMOTE_API_SOCKS_PORT` | Local port for the SOCKS5 proxy tunnel (default: `1080`). |
| `GCP_IAP_BASTION_INSTANCE_NAME` | Bastion VM name if different from the one in `.env`. |
| `GCP_BASTION_PROJECT` | Bastion GCP project if different from the one in `.env`. |
| `GCP_SECRET_PROJECT` | GCP project where the API token secret is stored (used by `get-api-token`). |
| `API_RECO_TOKEN_SECRET_NAME` | Name of the secret in GCP Secret Manager containing the API token (used by `get-api-token`). |
| `LOAD_TEST_V1_URL` | URL of the dedicated load-test Cloud Run instance for API v1 (used by `load-test-benchmark`). |
| `LOAD_TEST_V2_REDIS_URL` | URL of the dedicated load-test Cloud Run instance for API v2 with Redis (used by `load-test-benchmark`). |
| `LOAD_TEST_V2_NO_REDIS_URL` | URL of the dedicated load-test Cloud Run instance for API v2 without Redis (used by `load-test-benchmark`). |
