FROM astral/uv:0.11-python3.11-trixie

# Build arguments for configuration
ARG LOCAL=false
ARG GOOGLE_CLOUD_PROJECT

# Create non-root user early so COPY --chown can reference it
RUN groupadd --system --gid 999 appuser \
    && useradd --system --gid 999 --uid 999 appuser

# Allow uv to compile bytecode (faster init) and disable caching to reduce image size
ENV UV_COMPILE_BYTECODE=1
ENV UV_NO_CACHE=1

# Install libraries
WORKDIR /app
COPY ./pyproject.toml ./uv.lock ./
RUN uv sync --locked --no-dev

# Copy local code to the container
COPY ./src .
COPY ./src/huggy ./huggy

# Expose the application port and set environment variables
EXPOSE 8080
ENV GOOGLE_CLOUD_PROJECT=${GOOGLE_CLOUD_PROJECT}
ENV PYTHONUNBUFFERED=True

# If running locally, copy the application default credentials for Google Cloud authentication
RUN if [ "$LOCAL" = "true" ]; then \
    mkdir -p /root/.config/gcloud && \
    cp ./application_default_credentials.json /root/.config/gcloud/application_default_credentials.json; \
    fi

# Switch to non-root user for security
USER appuser

# Use uv to run the app with Gunicorn and Uvicorn workers
ENTRYPOINT ["uv", "run", "--no-dev", "gunicorn", "-k", "uvicorn.workers.UvicornWorker", "--bind", ":8080", "--workers", "8", "--threads", "2", "--preload", "--timeout", "0", "main:app"]
