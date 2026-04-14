FROM python:3.13-slim

# Build prerequisites
# Using uv for ultra-fast package management
COPY --from=ghcr.io/astral-sh/uv:0.11.6 /uv /bin/uv

# Set Environment variables
ENV PYTHONUNBUFFERED=True \
    APP_HOME=/app

WORKDIR $APP_HOME

# Install dependencies
# Copied first to leverage Docker layer caching
COPY ./pyproject.toml ./uv.lock ./
RUN uv sync --locked --no-dev

# Copy application code
COPY ./src ./

# Inject Cloud project configuration
ARG GOOGLE_CLOUD_PROJECT
ENV GOOGLE_CLOUD_PROJECT=${GOOGLE_CLOUD_PROJECT}

EXPOSE 8080

# Start server
CMD ["uv", "run", "gunicorn", "-k", "uvicorn.workers.UvicornWorker", "--bind", ":8080", "--workers", "8", "--threads", "2", "--preload", "--timeout", "0", "main:app"]
