SHELL := /bin/bash

# Variables can be overridden from the command line if needed
IMAGE_NAME       ?= elementary-data
API_NAME         ?= elementapi
SERVICE_NAME     ?= data-quality-app
TARGET_ENV       ?= local
REGISTRY         ?= europe-west1-docker.pkg.dev/passculture-infra-prod/pass-culture-artifact-registry
TAG              ?= latest
DOCKER_PORT      ?= 8081

.PHONY: install start start_with_gunicorn start_as_not_local \
        docker-build docker-run docker-push deploy compile_requirements

## Local development tasks

install:
	uv sync

start:
	@echo "Starting with Gunicorn (production simulation)..."
	cd src && API_LOCAL=True uv run gunicorn --bind :8081 --workers 1 --threads 10 --preload --timeout 0 main:app

start_as_not_local:
	@echo "Starting as if in production (without API_LOCAL flag)..."
	cd src && uv run gunicorn --bind :8081 --workers 1 --threads 10 --preload --timeout 0 main:app


# Build the Docker image. The Dockerfile can use the build-arg LOCAL
# to adapt behavior for local vs. production builds.
docker-build:
	@echo "Building Docker image '$(IMAGE_NAME)' for TARGET_ENV=$(TARGET_ENV)..."
	docker build . \
	  --build-arg LOCAL=$(TARGET_ENV) \
	  -t $(IMAGE_NAME)

# Run the Docker container locally.
docker-run:
	@echo "Running Docker container from image '$(IMAGE_NAME)' on port $(DOCKER_PORT)..."
	docker run -p $(DOCKER_PORT):$(DOCKER_PORT) -e LOCAL=$(TARGET_ENV) $(IMAGE_NAME)

# Tag and push the image to the remote registry.
docker-push:
	@echo "Tagging and pushing image to registry..."
	docker tag $(IMAGE_NAME) $(REGISTRY)/api-data/$(API_NAME):$(TAG)
	docker push $(REGISTRY)/api-data/$(API_NAME):$(TAG)

# Optionally, you can trigger deployment locally. In production, your GitHub Actions
# workflow uses deploy-cloudrun. This target could, for example, invoke a gcloud CLI command.
deploy:
	@echo "Deploying service '$(SERVICE_NAME)' using Cloud Run..."
	# Example (customize as needed):
	# gcloud run deploy $(SERVICE_NAME) \
	#    --image=$(REGISTRY)/api-data/$(API_NAME):$(TAG) \
	#    --region=europe-west1 \
	#    --project=<your-project-id>
	@echo "Deployment triggered."
