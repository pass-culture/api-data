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
└── services/         # External infrastructure clients (Vertex, DB, Logger)

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

### 4. Database Connection (Staging)
To develop locally, we connect to the Staging database using an SSH tunnel.
👉 **[Read the Notion guide on how to set up the SSH tunnel here](https://www.notion.so/passcultureapp/Communiquer-avec-la-base-de-donn-es-de-l-API-Recommendation-Staging-via-sa-machine-locale-2fead4e0ff98808989e9d02d45394904?source=copy_link)**

### 5. Install Dependencies
```bash
make install
```

### 6. Run the API
```bash
make start
```

### 7. Run Tests
```bash
make test
```
