########## ARGUMENT ##########
ARG network_mode=default

########## BASE ##########
FROM python:3.12-slim AS base

COPY --from=ghcr.io/astral-sh/uv:0.8.13 /uv /bin/uv

ENV PYTHONUNBUFFERED=True
ENV APP_HOME=/app
WORKDIR $APP_HOME

########## BUILDER DEFAULT ##########
FROM base AS builder-default

# Installer gcc et outils de compilation
RUN apt-get update && apt-get install -y gcc libc-dev libffi-dev && rm -rf /var/lib/apt/lists/*

COPY ./pyproject.toml ./
COPY ./uv.lock ./
COPY ./application_default_credentials.json ./

RUN uv sync --locked --no-dev

########## BUILDER PROXY ##########
FROM base AS builder-proxy

# Installer gcc et outils de compilation
RUN apt-get update && apt-get install -y gcc libc-dev libffi-dev && rm -rf /var/lib/apt/lists/*

COPY ./cacert.pem /cacert.pem
COPY ./pyproject.toml ./
COPY ./uv.lock ./
COPY ./application_default_credentials.json ./

RUN SSL_CERT_FILE=/cacert.pem uv sync --locked --no-dev

########## FINAL STAGE ##########
FROM builder-${network_mode} AS final

COPY ./src .
COPY ./src/huggy ./huggy

ARG LOCAL=false
ARG GOOGLE_CLOUD_PROJECT
ENV GOOGLE_CLOUD_PROJECT=${GOOGLE_CLOUD_PROJECT}
ENV SSL_CERT_FILE=/cacert.pem

EXPOSE 8080

RUN if [ "$LOCAL" = "true" ]; then \
    mkdir -p /root/.config/gcloud && \
    cp ./application_default_credentials.json /root/.config/gcloud/application_default_credentials.json; \
    fi

CMD ["uv", "run", "gunicorn", "-k", "uvicorn.workers.UvicornWorker", "--bind", ":8080", "--workers", "8", "--threads", "2", "--preload", "--timeout", "0", "main:app"]
