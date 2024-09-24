init:
	pyenv install 3.9 -s
	@eval "$$(pyenv init -)" && pyenv virtualenv 3.9 api-data-data-quality && pyenv local api-data-data-quality

install:
	@eval "$$(pyenv init -)" && pyenv activate api-data-data-quality && uv pip install -r requirements.txt

docker-run:
	export LOCAL=false
	docker build . -t data-quality-app
	docker run -p 8080:8080 data-quality-app
