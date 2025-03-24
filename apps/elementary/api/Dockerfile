FROM python:3.10-slim
COPY --from=ghcr.io/astral-sh/uv:0.3.4 /uv /bin/uv

ENV PYTHONUNBUFFERED=True
ENV APP_HOME=/app
WORKDIR $APP_HOME


# Install libraries
COPY ./requirements.txt ./
RUN uv pip install -r requirements.txt --system
COPY ./src .

# Conditionally copy the Google Cloud credentials file based on the argument
ARG LOCAL=false
ARG GOOGLE_CLOUD_PROJECT
ENV GOOGLE_CLOUD_PROJECT=${GOOGLE_CLOUD_PROJECT}
ENV PORT=8081
RUN if [ "$LOCAL" = "true" ]; then \
    mkdir -p /root/.config/gcloud && \
    cp ./application_default_credentials.json /root/.config/gcloud/application_default_credentials.json; \
    fi

# Run the container
CMD ["/bin/sh", "-c", "exec gunicorn main:app --workers 1 --log-level debug --timeout 300 --bind 0.0.0.0:${PORT}"]
