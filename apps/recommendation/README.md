# Data Recommendation API

Recommendation API with FastAPI + Psql + VertexAI endpoints

## See <uri-api>/docs for API endpoints

## Folders structure

```
+-- src
| + huggy
|  +-- core
|    +-- endpoint - configuration of VertexAi endpoint for retrieval and ranking
|    +-- model_engine - orchestration of the scoring pipeline
|    +-- model_selection - model selection based on the model_endpoint parameter
|    +-- scorer - retrieve the base of recommendable offers and score them
|  +-- crud - functions for reading/writing to the database
|  +-- database - logic for handling db connexion
|  +-- models - model of the database tables - 1 file per table
|  +-- schemas - definition of object properties
|  +-- utils
|  +-- views - router views
|
+-- main.py
|
+-- tests - tests files
```

## How to DEV

### Set-up a dev-env:

Install pyenv and install `python 3.9``

```sh
pyenv install 3.12
```

Create a virtual env
```sh
pyenv virtualenv 3.12 reco_fastapi
pyenv shell reco_fastapi
```

```sh
cd apps/recommendation/api/
make install
```

### Run tests

```sh
cd apps/recommendation/api && make test
```

#### Troubleshooting If you have issues with the psycopg2 installation

Connect to db, create db database, add postgis extension
```sh

docker exec -it <docker_id> /bin/sh
psql -U postgres

create database db;
\c db;
create extension postgis;
```

### Run it locally

```sh
cd apps/recommendation/api/src
make start
```

## How to PROD

### CI-CD

github-actions handle de CI/CD deployment

- we have a `main` (testing), `staging` and `production` branches that deploy for each environment. Everything is done automatically.

#### Deploy by hand

In case of emergency you still can deploy the api by hand:


**1:** Build

```
cd apps/recommendation/api
gcloud builds submit \
  --tag eu.gcr.io/<PROJECT-ID>/data-gcp/<IMAGE-NAME>

```
- PROJECT-ID : (passculture-data-\<env>)
- IMAGE-NAME : (api-recommendation-\<env>)

**2:** Deploy

```
cd apps/recommendation/api

gcloud run deploy <SERVICE> \
--image <IMAGE>:latest \
--region europe-west1 \
--allow-unauthenticated \
--platform managed

```
- SERVICE : Service Name (api-recommendation-\<env>)
- IMAGE : Docker image (eu.gcr.io/passculture-data-\<env>/data-gcp/api-recommendation)


**Staging**
```sh
gcloud builds submit --tag eu.gcr.io/passculture-data-ehp/data-gcp/apireco-stg

gcloud run deploy apireco-stg \
--image eu.gcr.io/passculture-data-ehp/data-gcp/apireco-stg:latest \
--region europe-west1 \
--allow-unauthenticated \
--platform managed
```

**Prod**
```sh
gcloud builds submit --tag eu.gcr.io/passculture-data-prod/data-gcp/apireco-prod

gcloud run deploy apireco-prod \--image eu.gcr.io/passculture-data-prod/data-gcp/apireco-prod:latest \
--region europe-west1 \
--allow-unauthenticated \
--platform managed
```
