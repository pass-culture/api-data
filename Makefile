SHELL := /bin/bash

ruff_fix:
	uv run ruff check --fix
	uv run ruff format

ruff_check:
	uv run ruff check
	uv run ruff format --check

install:
	uv venv --python 3.9
	uv sync
