#!/bin/bash

export DATA_GCP_TEST_POSTGRES_PORT=5432
export DB_NAME="db"
export PYTHONPATH=$PYTHONPATH:$(pwd)

if [ "$CI" '=' true ]
then
  export PG_HOST="postgres"
else
  export PG_HOST="localhost"
fi

[ "$CI" '!=' true ] && docker-compose up -d testdb
function wait_for_container () {(
    until PGPASSWORD=postgres psql -h $PG_HOST -p $DATA_GCP_TEST_POSTGRES_PORT -U "postgres" -c '\q'; do
      >&2 echo "Postgres is unavailable - sleeping"
      sleep 2
    done
)}
function run () {(
    pytest --cov
)}
sleep 3
wait_for_container
run
echo "Debug :  execute RUN"
status=$?

[ "$CI" '!=' true ] && docker-compose stop testdb && docker-compose rm -f testdb

exit $status
