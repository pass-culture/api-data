FROM astral/uv:0.11-python3.11-trixie-slim

# Conditionally copy the Google Cloud credentials file based on the argument
ARG LOCAL=false
ARG GOOGLE_CLOUD_PROJECT

# Create non-root user early
RUN groupadd --system --gid 999 appuser \
    && useradd --system --gid 999 --uid 999 --create-home appuser

# Allow uv to compile bytecode (faster init) and disable caching to reduce image size
ENV UV_COMPILE_BYTECODE=1
ENV UV_NO_CACHE=1

# Install libraries
WORKDIR /app
COPY ./pyproject.toml ./uv.lock ./
RUN uv sync --locked --no-dev

# Copy application code
COPY ./src .

# Conditionally copy the Google Cloud credentials file based on the argument
EXPOSE 8080
ENV GOOGLE_CLOUD_PROJECT=${GOOGLE_CLOUD_PROJECT}
ENV PYTHONUNBUFFERED=True

# If running locally, copy the application default credentials for Google Cloud authentication
RUN if [ "$LOCAL" = "true" ]; then \
    mkdir -p /home/appuser/.config/gcloud && \
    cp ./application_default_credentials.json /home/appuser/.config/gcloud/application_default_credentials.json && \
    chown -R appuser:appuser /home/appuser/.config; \
    fi

# Create Log directory and set permissions
RUN mkdir -p /app/logs && chown appuser:appuser /app/logs

# Switch to non-root user for security
USER appuser

# Use uv to run the app with Gunicorn and Uvicorn workers
ENTRYPOINT ["uv", "run", "--no-dev", "gunicorn", "-k", "uvicorn.workers.UvicornWorker", "--bind", ":8080", "--workers", "1", "--threads", "10", "--preload", "--timeout", "0", "main:app"]
