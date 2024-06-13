init:
	pyenv install 3.9 -s
	@eval "$$(pyenv init -)" && pyenv virtualenv 3.9 api-data-fraud-compliance && pyenv local api-data-fraud-compliance

install_with_uv:
	@eval "$$(pyenv init -)" && pyenv activate api-data-fraud-compliance && uv pip install -r dev-requirements.txt

install:
	@eval "$$(pyenv init -)" && pyenv activate api-data-fraud-compliance && pip install -r dev-requirements.txt

start:
	@eval "$$(pyenv init -)" && cd src && API_LOCAL=True uvicorn main:app --reload

guvistart:
	@eval "$$(pyenv init -)" && cd src && API_LOCAL=True gunicorn -k uvicorn.workers.UvicornWorker --workers 1 --threads 10 --preload --timeout 0 main:app