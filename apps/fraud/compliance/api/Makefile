SHELL := /bin/bash

PYTHON_VERSION := 3.10
EXTRA_INDEX := https://pypi.org/simple
INDEX_URL := https://download.pytorch.org/whl/cpu

install:
	UV_VENV_CLEAR=1 uv venv --python $(PYTHON_VERSION) && source .venv/bin/activate && uv sync --index-url $(INDEX_URL) --extra-index-url $(EXTRA_INDEX) --python $(PYTHON_VERSION)

start:
	source .venv/bin/activate && cd src && API_LOCAL=True uvicorn main:app --reload

start_with_gunicorn:
	source .venv/bin/activate && cd src && API_LOCAL=True gunicorn -k uvicorn.workers.UvicornWorker --bind :8000 --workers 1 --threads 10 --preload --timeout 0 main:app

start_as_not_local:
	source .venv/bin/activate && cd src && uvicorn main:app --reload
