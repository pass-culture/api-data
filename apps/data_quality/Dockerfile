FROM python:3.10-slim
COPY --from=ghcr.io/astral-sh/uv:0.3.4 /uv /bin/uv

ENV PYTHONUNBUFFERED=True
ENV APP_HOME=/app
WORKDIR $APP_HOME


# Install libraries
COPY ./requirements.txt ./
RUN uv pip install -r requirements.txt --system
COPY ./app .
COPY ./secret/sa.gcpkey.json ./app/sagcpkey.json
ENV GOOGLE_APPLICATION_CREDENTIALS="./app/sagcpkey.json"

EXPOSE 8080

# Commande pour démarrer Gunicorn
CMD ["gunicorn", "main:app", "--workers", "1", "--log-level", "debug", "--timeout", "300", "--bind", "0.0.0.0:8080"]
