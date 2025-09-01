SHELL := /bin/bash

EXTRA_INDEX := https://pypi.org/simple
INDEX_URL := https://download.pytorch.org/whl/cpu

install:
	UV_VENV_CLEAR=1 uv venv && uv sync --index-url $(INDEX_URL) --extra-index-url $(EXTRA_INDEX)

start:
	cd src && API_LOCAL=True uv run uvicorn main:app --reload

start_with_gunicorn:
	cd src && API_LOCAL=True uv run gunicorn -k uvicorn.workers.UvicornWorker --bind :8000 --workers 1 --threads 10 --preload --timeout 0 main:app

start_as_not_local:
	cd src && uv run uvicorn main:app --reload
