# API validation

Code source de l'api de validation d'offres.
API FastAPI avec uvicorn déployée dans Cloud Run.

Api créée en suivant : <https://cloud.google.com/run/docs/quickstarts/build-and-deploy?hl=fr#python>

## Routes

La liste des routes à jour est disponible sur l'API Swagger :

- en local : `make start` et aller sur <http://localhost:8000/latest/docs>
- [Swagger Dev](https://compliance.testing.passculture.team/latest/docs)
- [Swagger Staging](https://compliance.staging.passculture.team/latest/docs)
- [Swagger Prod](https://compliance.passculture.team/latest/docs)

## Tests

### Tests unitaires

Pour lancer les tests :

```bash
pytest
```

### Tests d'intégration

**Objectif:**
L'objectif des tests d'intégration est de vérifier le bon fonctionnement de l'api dans son ensemble. C'est à dire son fonctionnement ainsi que la communication entre l'api et les autres services (CloudSQL, AI Platform...).

**Fonctionnement:**
On utilise postman et newman pour faire ces tests d'intégration.
Les tests vont appeler toutes les routes de l'API et vérifier qu'elle renvoit ce qui est attendu.

**En pratique:**
Pour modifier les tests, ouvrir les fichiers du dossier `/postman` avec Postman, les modifier via l'UI, et les exporter de nouveau. (On peut aussi modifier directement les jsons mais ce n'est pas très lisible.)

Le dossier contient:

- \<env>.postman_environement.json: les valeurs des variables d'environnement (par ex : {api_url})
- api_validation_tests.postman_collection.json: Les appels et les tests à faire.

**Ressources:**

- Comment écrire des tests avec postman: <https://learning.postman.com/docs/writing-scripts/test-scripts/>
- Exemples de scripts de test: <https://learning.postman.com/docs/writing-scripts/script-references/test-examples/>

## Déploiement local

### Pour tester l'API en local

1. Récupérer les paths des modèles sur GCS via l'App MLFlow : [GSC_PATH_COMPLIANCE](https://mlflow.staging.passculture.team/#/models/compliance_default_stg) et le [GSC_PATH_OFFER_CATEGORISATION](https://mlflow.staging.passculture.team/#/models/offer_categorisation_stg) :
    - Cliquer sur la version du modèle désirée (la dernière par exemple)
    - Cliquer sur le lien après "Source Run:", en haut de la page
    - On arrive sur la page du run qui a généré le modèle. Cliquer sur model.cb
    - Récupérer le full GCP Path (gs://...)
2. Telecharger le model en local

    ```bash
    dans le dossier 'apps/fraud/compliance/api/'
    ```

3. Installer le projet et les requirements
    - `make init` pour créer le virtualenv
    - `make install`

4. Lancer l'API

    ```bash
    make start
    ```

### Pour l'image Docker

```bash
cd apps/fraud/validation/api/
source ./deploy_local.sh
```

## Déploiement sur GCP

>Le déploiement est fait **automatiquement** via un job CircleCI pour les environements de **staging** et de **production**.

------

**Etape 1:** Conteneuriser l'image

```bash
cd apps/fraud/validation/api/
gcloud builds submit \
  --tag eu.gcr.io/<PROJECT-ID>/data-gcp/<IMAGE-NAME> \

```

- PROJECT-ID : L'id du projet (passculture-data-\<env>)
- IMAGE-NAME : Le nom de l'image (api-compliance-\<env>)

En dev ça donne:

```bash
gcloud builds submit --tag eu.gcr.io/passculture-data-ehp/data-gcp/api-compliance-dev
```

En stg ça donne:

```bash
gcloud builds submit --tag eu.gcr.io/passculture-data-ehp/data-gcp/api-compliance-stg
```

------

**Etape 2:** Déployer une révision sur Cloud Run

>Si demandé toujours choisir les options:
>
>- target platform: "Cloud Run (fully managed)"
>- region: "europe-west1"

```bash
cd recommendation/api

gcloud run deploy <SERVICE> \
--image <IMAGE>:latest \
--region europe-west1 \
--allow-unauthenticated \
--platform managed
```

- SERVICE : nom du service Cloud Run a redéployer (apivalidation-\<env>)
- IMAGE : L'url de l'image à déployer (eu.gcr.io/passculture-data-\<env>/data-gcp/api-compliance)

En dev ça donne:

```bash
gcloud run deploy api-compliance-dev \
--image eu.gcr.io/passculture-data-ehp/data-gcp/api-compliance-dev:latest \
--region europe-west1 \
--allow-unauthenticated \
--platform managed
```

En stg ça donne:

```bash
gcloud run deploy api-compliance-stg \
--image eu.gcr.io/passculture-data-ehp/data-gcp/api-compliance-stg:latest \
--region europe-west1 \
--allow-unauthenticated \
--platform managed
```

## Infos utiles

- Les variables d'environnement sont définies dans le code terraform du cloud run.
