SHELL:=/bin/bash

install:
	UV_VENV_CLEAR=1 uv venv -p 3.9 && uv sync

start:
	source .venv/bin/activate && cd src && API_LOCAL=1 uvicorn main:app --reload
