# Data Recommendation API V2

Recommendation API V2 with FastAPI + Psql + VertexAI endpoints

## See <uri-api>/docs for API endpoints

## Folder structure
```
src/
├── api/          # Routes (Controllers)
├── core/         # Recommendation engine (algorithms, scoring, etc.)
│   ├── pipeline.py   # Main orchestrator
│   ├── retrieval.py  # Offer retrieval (DB/Vertex)
│   ├── ranking.py    # Sorting and scoring
│   └── filters.py    # Diversification and business rules
├── services/     # External clients (Vertex, Database)
├── config/       # Configuration (YAML & environment variables)
└── schemas/      # Pydantic models (I/O)

tests/
├── api/             # Route tests (Controllers)
└── conftest.py      # Common fixtures
```

## How to DEV

### Pre-requisite:

Install uv, a tool for managing Python versions and virtual environments:

```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
```

### Install dependencies
```sh
make install
```

### Run the API
```sh
make start
```

### Run tests
```sh
make test
```
