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



Here is the step-by-step lifecycle of a single request:

### 1. 👤 Contextualization (`core/context.py`, `core/geo.py`)
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
├── connectors/       # Adapters bridging core logic and external services (e.g., VertexAPI)
├── core/             # Core recommendation engine logic
│   ├── pipeline.py         # 1. Main orchestrator tying all steps together
│   ├── context.py          # 2. User state management & ML feature engineering
│   ├── geo.py              # 3. PostGIS spatial queries for user location
│   ├── retrieval.py        # 4. Candidate fetching & Spatial routing
│   ├── ranking.py          # 5. Scoring via Vertex Ranking
│   ├── diversification.py  # 6. Business rules & Round-Robin mixing
│   └── tracking.py         # 7. GCP Logging for BigQuery ingestion
├── models/           # SQLAlchemy database models (PostGIS/DB schema)
├── schemas/          # Pydantic models (Input/Output strict validation)
├── services/         # External infrastructure clients (Vertex, DB, Logger)
└── streamlit/        # Local Streamlit UI acting as a visual proxy for the API

tests/
├── api/              # Route integration tests
└── conftest.py       # Pytest common fixtures
```

---

## 🛠️ How to DEV (Local Environment)

### 1. Prerequisites
We use `uv`, an ultra-fast tool for managing Python versions and virtual environments:
```bash
curl -LsSf [https://astral.sh/uv/install.sh](https://astral.sh/uv/install.sh) | sh
```

### 2. Environment Setup
Configuration is managed via environment variables. Start by duplicating the template to create your local environment file:
```bash
cp .env.template .env
```
*Fill in the missing values in your `.env` file according to the instructions below.*

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

### 5. Run the API (with Staging Database)
To develop locally, we connect to the Staging database using an automated SSH tunnel. The following command securely opens the tunnel in the background, starts the API, and gracefully closes the tunnel when you exit:

```bash
make start-with-remote-db
```
*Troubleshooting: If the SSH tunnel fails to establish via the command above, check your .env variables or 👉 **[Read the Notion guide on how to set up the SSH tunnel manually](https://www.notion.so/passcultureapp/Communiquer-avec-la-base-de-donn-es-de-l-API-Recommendation-Staging-via-sa-machine-locale-2fead4e0ff98808989e9d02d45394904?source=copy_link)**.*

(Note: If you are running a fully local database instance, you can bypass the tunnel and simply run make start).

### 6. Run the API & Streamlit Proxy UI (Recommended for Testing)
To test the API easily, configure filters, simulate user states (e.g., active or cold start), and visually inspect the returned offers, a local Streamlit UI is available.

Run the tunnel, FastAPI server, and Streamlit frontend all together using:
```bash
make dev-with-streamlit
```
*Once running, navigate to the local URL provided by Streamlit. When finished, press `Ctrl+C` in your terminal to gracefully shut down the UI, API, and SSH tunnel simultaneously.*

### 7. Run Tests
```bash
make test
```

## 🔌 Accessing Staging Environment (Swagger & Tokens)

To debug or inspect the legacy V1 API in the staging environment (which is protected inside a VPC), we provide dedicated Makefile commands to automate the secure tunnel connection.

### 1. Access V1 Swagger UI
This command opens a SOCKS proxy tunnel to the VPC and launches a configured Chrome instance to access the internal Swagger UI.

```bash
make access-swagger-api-v1
```
*👉 **[Read the Notion guide on how to access Cloud Run VPC APIs via SOCKS tunnel](https://www.notion.so/passcultureapp/Consulter-le-Swagger-d-une-API-Cloud-Run-VPC-Interne-en-local-via-un-tunnel-SOCKS-321ad4e0ff9880bea690ca240965d5a9?source=copy_link)**.*

### 2. Get Staging API Token
Retrieve a valid Bearer token for the staging environment (useful for Authorizing requests in the Swagger UI).

```bash
make get-staging-api-token
```
*Note: This requires `gcloud` to be authenticated.*

---

## ⚙️ Configuration Reference

The application relies on environment variables for configuration. Copy `.env.template` to `.env` and fill in the values.
**Note:** For security reasons, sensitive values (IPs, passwords, project IDs) are not committed. Ask the Data Science team for the correct values or check the internal documentation.

### 🌐 API Server
| Variable | Description |
|----------|-------------|
| `FASTAPI_SERVER_PORT` | The local port where the FastAPI server will run (e.g., `8801`). |

### 🗄️ Database Connection
Used to connect to the PostgreSQL database. When running locally with `make start-with-remote-db`, these should point to the **local end of the SSH tunnel**.

| Variable | Description |
|----------|-------------|
| `SQL_HOST` | Hostname of the DB. Usually `127.0.0.1` when using the tunnel. |
| `SQL_PORT` | Local port forwarded to the remote DB. |
| `SQL_BASE` | Name of the database. |
| `SQL_BASE_USER` | Database username. |
| `SQL_BASE_PASSWORD` | Database password. |

### 🧠 Google Cloud & Vertex AI
Configuration for the Recommendation Engine's ML backend.

| Variable | Description |
|----------|-------------|
| `GCP_PROJECT` | GCP Project ID where the Vertex AI endpoints are hosted. |
| `VERTEX_RETRIEVAL_ENDPOINT_NAME` | Name of the Vertex AI Endpoint for the Retrieval model. |
| `VERTEX_RANKING_ENDPOINT_NAME` | Name of the Vertex AI Endpoint for the Ranking model. |

### 🏗️ Infrastructure & SSH Tunnels
These variables are used by the `Makefile` to establish secure tunnels to the VPC (for DB access and Swagger access).

| Variable | Description |
|----------|-------------|
| `GCP_ZONE` | GCP Zone where the Bastion VM is located. |
| `GCP_IAP_BASTION_INSTANCE_NAME` | Name of the Bastion VM (Tinyproxy) used for the tunnel. |
| `REMOTE_SQL_GCP_PROJECT` | GCP Project ID where the Cloud SQL instance is hosted. |
| `REMOTE_SQL_HOST` | Internal Private IP of the Cloud SQL instance. |
| `REMOTE_SQL_PORT` | Port of the remote Postgres instance (e.g., `5432`). |

### 🔌 V1 Swagger Proxy (Legacy)
Used by `make access-swagger-api-v1` to browse the internal API V1 documentation.

| Variable | Description |
|----------|-------------|
| `RECOMMENDATION_V1_STAGING_SOCKS_PORT` | Local port to use for the SOCKS5 proxy tunnel. |
| `RECOMMENDATION_V1_STAGING_CLOUDRUN_URL` | Full internal URL of the Staging Swagger UI to open (Cloud Run). |

### 🔐 Secrets Management
Used by `make get-staging-api-token` to fetch secrets from Google Secret Manager.

| Variable | Description |
|----------|-------------|
| `GCP_SECRET_PROJECT` | GCP Project ID where secrets are stored. |
| `API_RECO_TOKEN_SECRET_NAME` | Name of the secret in Secret Manager containing the API Token. |

### 🛠️ Debugging & Logs
| Variable | Description |
|----------|-------------|
| `LOGS_PRETTY_PRINT` | Set to `1` to enable colored, human-readable JSON logs for local dev. |
| `ENABLE_TRACKING_LOGS` | Set to `0` to disable sending tracking events to BigQuery (avoids pollution during dev). |
| `SWAGGER_UI_EXAMPLE_USER_ID` | A valid User ID to pre-fill in the Swagger UI "Execute" fields for testing. |
