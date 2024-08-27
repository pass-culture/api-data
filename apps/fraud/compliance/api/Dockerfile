FROM python:3.10-slim
COPY --from=ghcr.io/astral-sh/uv:0.3.4 /uv /bin/uv

ENV PYTHONUNBUFFERED True
ENV APP_HOME /app
WORKDIR $APP_HOME

# Install libraries
COPY ./requirements.txt ./
RUN uv pip install -r requirements.txt --system

# Run the container
COPY ./src .
CMD exec gunicorn -k uvicorn.workers.UvicornWorker --bind :$PORT --workers 1 --threads 10 --preload --timeout 0 main:app
