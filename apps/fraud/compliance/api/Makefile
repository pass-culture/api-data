SHELL := /bin/bash

install:
	uv venv --python 3.10
	source .venv/bin/activate && UV_EXTRA_INDEX_URL=https://download.pytorch.org/whl/cpu uv pip sync dev-requirements.txt --index-strategy unsafe-best-match

start:
	source .venv/bin/activate && cd src && API_LOCAL=True uvicorn main:app --reload

start_with_gunicorn:
	source .venv/bin/activate && cd src && API_LOCAL=True gunicorn -k uvicorn.workers.UvicornWorker --bind :8000 --workers 1 --threads 10 --preload --timeout 0 main:app

start_as_not_local:
	source .venv/bin/activate && cd src && uvicorn main:app --reload

compile_requirements:
	UV_EXTRA_INDEX_URL=https://download.pytorch.org/whl/cpu uv pip compile requirements.in -o requirements.txt --index-strategy unsafe-best-match
	UV_EXTRA_INDEX_URL=https://download.pytorch.org/whl/cpu uv pip compile dev-requirements.in -o dev-requirements.txt --index-strategy unsafe-best-match
