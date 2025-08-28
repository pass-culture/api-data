FROM python:3.10-slim

COPY --from=ghcr.io/astral-sh/uv:0.4.23 /uv /bin/uv

ENV PYTHONUNBUFFERED=True
ENV APP_HOME=/app
WORKDIR $APP_HOME

# Install libraries
COPY ./pyproject.toml ./
ENV UV_PROJECT_ENVIRONMENT="/usr/local/"
ENV PYTHON_VERSION=3.10
ENV UV_INDEX_URL=https://download.pytorch.org/whl/cpu
ENV UV_EXTRA_INDEX_URL=https://pypi.org/simple
RUN uv sync --index-url $UV_INDEX_URL --extra-index-url $UV_EXTRA_INDEX_URL --python $PYTHON_VERSION
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
CMD exec gunicorn -k uvicorn.workers.UvicornWorker --bind :$PORT --workers 1 --threads 10 --preload --timeout 0 main:app
