FROM python:3.10-slim

COPY --from=ghcr.io/astral-sh/uv:0.8.13 /uv /bin/uv

ENV PYTHONUNBUFFERED=True
ENV APP_HOME=/app
WORKDIR $APP_HOME

# Install libraries
COPY ./pyproject.toml ./
COPY ./uv.lock ./
ENV UV_INDEX_URL=https://download.pytorch.org/whl/cpu
ENV UV_EXTRA_INDEX_URL=https://pypi.org/simple
RUN uv sync --locked --no-dev --index-url $UV_INDEX_URL --extra-index-url $UV_EXTRA_INDEX_URL
COPY ./src .

# Conditionally copy the Google Cloud credentials file based on the argument
ARG LOCAL=false
ARG GOOGLE_CLOUD_PROJECT
ENV GOOGLE_CLOUD_PROJECT=${GOOGLE_CLOUD_PROJECT}
ENV PORT=8080

RUN if [ "$LOCAL" = "true" ]; then \
    mkdir -p /root/.config/gcloud && \
    cp ./application_default_credentials.json /root/.config/gcloud/application_default_credentials.json; \
    fi

# Run the container
CMD exec uv run gunicorn -k uvicorn.workers.UvicornWorker --bind :$PORT --workers 1 --threads 10 --preload --timeout 0 main:app
