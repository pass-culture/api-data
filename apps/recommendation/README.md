# Data Recommendation API 

## See <uri-api>/docs for API endpoints


## How to DEV

### Set-up a dev-env: 

Install pyenv and install `python 3.9``

```sh
pyenv install 3.9
```

Create a virtual env
```sh 
pyenv virtualenv 3.9 reco_fastapi
pyenv shell reco_fastapi
```

```sh 
pip3 install -r requirements.txt
```

### Run tests


Set up a testdb :
```sh
export DATA_GCP_TEST_POSTGRES_PORT=5432
export DB_NAME="db"
docker-compose up -d testdb  
```
```sh
cd ~/apps/recommendation/
pyenv shell reco_fastapi
pytest
```

In case you have some troubles to run tests 

Connect to db, create db database, add postgis extension
```sh 
docker exec -it <docker_id> /bin/sh
psql -U postgres

create database db
\c db; 
create extension postgis;
```

### Run it locally

```sh
cd ~/apps/recommendation/api/src
uvicorn main:app --reload
```

## How to PROD

### CI-CD
 
github-actions handle de CI/CD deployment

- we have a `main` (testing), `staging` and `production` branches that deploy for each environment. Everything is done automatically.

#### Deploy by hand

In case of emergency you still can deploy the api by hand: 


**1:** Build

```
cd ~/apps/recommendation/api
gcloud builds submit \
  --tag eu.gcr.io/<PROJECT-ID>/data-gcp/<IMAGE-NAME>

```
- PROJECT-ID : (passculture-data-\<env>)
- IMAGE-NAME : (api-recommendation-\<env>)

**2:** Deploy

```
cd ~/apps/recommendation/api

gcloud run deploy <SERVICE> \
--image <IMAGE>:latest \
--region europe-west1 \
--allow-unauthenticated \
--platform managed

```
- SERVICE : Service Name (api-recommendation-\<env>)
- IMAGE : Docker image (eu.gcr.io/passculture-data-\<env>/data-gcp/api-recommendation)
