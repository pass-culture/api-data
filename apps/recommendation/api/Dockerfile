FROM python:3.9-slim

COPY --from=ghcr.io/astral-sh/uv:0.4.23 /uv /bin/uv

ENV PYTHONUNBUFFERED True

ENV APP_HOME /app
WORKDIR $APP_HOME

# Install libraries
COPY ./pyproject.toml ./
RUN uv sync --no-dev

# Copy local code to the container
COPY ./src .
COPY ./src/huggy ./huggy
EXPOSE 8080
CMD ["uv", "run", "gunicorn", "-k", "uvicorn.workers.UvicornWorker", "--bind", ":8080", "--workers", "8", "--threads", "2", "--preload", "--timeout", "0", "main:app"]
