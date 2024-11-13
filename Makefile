SHELL := /bin/bash

ruff-fix:
	ruff check --fix
	ruff format


ruff-check:
	ruff format --check
	ruff check

install:
	uv venv --python 3.9
	source .venv/bin/activate && uv pip install -r linter-requirements.txt
	source .venv/bin/activate && pre-commit install
