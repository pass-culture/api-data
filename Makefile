ruff-fix:
	ruff check --fix
	ruff format

ruff-check:
	ruff format --check
	ruff check

install:
	pyenv virtualenv --force 3.9 data-api-base
	pyenv local data-api-base
	@eval "$$(pyenv init -)" && pyenv activate data-api-base && uv pip install -r linter-requirements.txt && pre-commit install && make get_iap_refresh_token

get_iap_refresh_token:
	python scripts/get_iap_refresh_token.py
