SHELL := /bin/bash

install:
	uv venv --python 3.10 && uv pip install -r dev-requirements.txt

start:
	source .venv/bin/activate && cd src && API_LOCAL=True uvicorn main:app --reload

start_with_gunicorn:
	source .venv/bin/activate && cd src && API_LOCAL=True gunicorn -k uvicorn.workers.UvicornWorker --bind :8000 --workers 1 --threads 10 --preload --timeout 0 main:app

start_as_not_local:
	source .venv/bin/activate && cd src && uvicorn main:app --reload
