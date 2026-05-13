FROM astral/uv:0.11-python3.13-trixie-slim

# Build arguments for configuration
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

# Copy application code
COPY ./src .

# Expose the application port and set environment variables
EXPOSE 8080
ENV GOOGLE_CLOUD_PROJECT=${GOOGLE_CLOUD_PROJECT}
ENV PYTHONUNBUFFERED=True

# Switch to non-root user for security
USER appuser

# Start server
CMD ["uv", "run", "--no-dev", "gunicorn", "-k", "uvicorn.workers.UvicornWorker", "--bind", ":8080", "--workers", "8", "--preload", "--timeout", "0", "--control-socket", "/tmp/gunicorn.ctl", "main:app"]
