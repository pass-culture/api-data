FROM python:3.9-slim

COPY --from=ghcr.io/astral-sh/uv:0.8.13 /uv /bin/uv

ENV PYTHONUNBUFFERED True
ENV APP_HOME /app
WORKDIR $APP_HOME

# Install libraries
COPY ./pyproject.toml ./
COPY ./uv.lock ./
RUN uv sync --locked --no-dev

# Copy local code to the container
COPY ./src .
COPY ./src/huggy ./huggy

ARG LOCAL=false
ARG GOOGLE_CLOUD_PROJECT
ENV GOOGLE_CLOUD_PROJECT=${GOOGLE_CLOUD_PROJECT}
EXPOSE 8080

RUN if [ "$LOCAL" = "true" ]; then \
    mkdir -p /root/.config/gcloud && \
    cp ./application_default_credentials.json /root/.config/gcloud/application_default_credentials.json; \
    fi

CMD ["uv", "run", "gunicorn", "-k", "uvicorn.workers.UvicornWorker", "--bind", ":8080", "--workers", "8", "--threads", "2", "--preload", "--timeout", "0", "main:app"]
