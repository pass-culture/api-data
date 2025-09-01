SHELL:=/bin/bash

install:
	UV_VENV_CLEAR=1 uv venv && uv sync

start:
	cd src && API_LOCAL=1 uv run uvicorn main:app --reload
