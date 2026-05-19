SHELL := /bin/bash

install:
	UV_VENV_CLEAR=1 uv venv && uv sync --locked

start:
	cd src && API_LOCAL=True uv run uvicorn main:app --reload

start_with_gunicorn:
	cd src && API_LOCAL=True uv run gunicorn -k uvicorn.workers.UvicornWorker --bind :8000 --workers 1 --threads 10 --preload --timeout 0 main:app

start_as_not_local_dev:
	cd src && uv run uvicorn main:app --reload

start_as_not_local_stg:
	cd src && ENV_SHORT_NAME=stg uv run uvicorn main:app --reload

build_and_run_locally_in_docker:
	cp ~/.config/gcloud/application_default_credentials.json src/
	docker build . -t compliance --build-arg LOCAL=true
	rm src/application_default_credentials.json
	docker run -p 8080:8080 compliance:latest -e API_LOCAL=true
