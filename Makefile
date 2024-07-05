ruff-format:
	ruff check --select I --fix # sort imports
	ruff format # format


ruff-check:
	ruff format --check
	ruff check --fix
