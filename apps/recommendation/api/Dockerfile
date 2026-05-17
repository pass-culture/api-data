FROM python:3.11-slim

COPY --from=ghcr.io/astral-sh/uv:0.10.9 /uv /bin/uv

ENV PYTHONUNBUFFERED True
ENV APP_HOME /app
WORKDIR $APP_HOME

# Install libraries
COPY ./pyproject.toml ./
COPY ./uv.lock ./
RUN uv sync --locked --no-dev

RUN mkdir -p /.cache/uv
RUN chown 1000 /.cache/uv && chown -R 1000 $APP_HOME/.venv

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

USER 1000

CMD ["uv", "run", "gunicorn", "-k", "uvicorn.workers.UvicornWorker", "--bind", ":8080", "--workers", "8", "--threads", "2", "--preload", "--timeout", "0", "main:app"]
