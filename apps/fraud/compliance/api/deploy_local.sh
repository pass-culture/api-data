if [ ! -f ~/.config/gcloud/application_default_credentials.json ]; then
    gcloud auth application-default login
fi
cp ~/.config/gcloud/application_default_credentials.json src/application_default_credentials.json
docker build -t pcpapillon --build-arg LOCAL=true --build-arg GOOGLE_CLOUD_PROJECT=passculture-data-ehp .
rm src/application_default_credentials.json
docker run -p 8080:8080 -e "PORT=8080" pcpapillon
