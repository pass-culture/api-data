SHELL:=/bin/bash

install:
	uv venv -p 3.9 && uv pip install -r requirements.txt

start:
	source .venv/bin/activate && cd src && API_LOCAL=1 uvicorn main:app --reload

compile_requirements:
	source .venv/bin/activate && uv pip compile requirements.in
