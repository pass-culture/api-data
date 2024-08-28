init:
	pyenv install 3.10 -s
	@eval "$$(pyenv init -)" && pyenv virtualenv 3.9 api-data-fraud-compliance && pyenv local api-data-fraud-compliance

install_with_uv:
	@eval "$$(pyenv init -)" && pyenv activate api-data-fraud-compliance && uv pip install -r dev-requirements.txt

install:
	@eval "$$(pyenv init -)" && pyenv activate api-data-fraud-compliance && pip install -r dev-requirements.txt

start:
	@eval "$$(pyenv init -)" && cd src && API_LOCAL=True uvicorn main:app --reload

start_with_gunicorn:
	@eval "$$(pyenv init -)" && cd src && API_LOCAL=True gunicorn -k uvicorn.workers.UvicornWorker --bind :8000 --workers 1 --threads 10 --preload --timeout 0 main:app

start_as_not_local:
	@eval "$$(pyenv init -)" && cd src && uvicorn main:app --reload
