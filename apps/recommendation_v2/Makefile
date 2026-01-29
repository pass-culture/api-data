SHELL:=/bin/bash

install:
	UV_VENV_CLEAR=1 uv venv && uv sync --locked

start:
	cd src && uv run uvicorn main:app --reload

test:
	pytest ./tests
