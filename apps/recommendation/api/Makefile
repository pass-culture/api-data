init:
	pyenv install 3.9 -s
	@eval "$$(pyenv init -)" && pyenv virtualenv 3.9 api-data-reco && pyenv local api-data-reco

install_with_uv:
	@eval "$$(pyenv init -)" && pyenv activate api-data-reco && uv pip install -r requirements.txt

install:
	@eval "$$(pyenv init -)" && pyenv activate api-data-reco && pip install -r requirements.txt

start:
	@eval "$$(pyenv init -)" && cd src && API_LOCAL=1 uvicorn main:app --reload
