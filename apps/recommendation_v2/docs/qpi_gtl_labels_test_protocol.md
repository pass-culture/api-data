# Protocole de test — QPI → GTL labels (playlist recommendation)

Ce document décrit comment reproduire en local le test de bout en bout de la fonctionnalité
"QPI (Quiz de Préférences Initial) → résolution des GTL labels" dans le pipeline
`generate_playlist_recommendations` (`recommendation_v2`).

## Pré-requis

- `pass-culture-main/api` démarré en local (Flask, `command python src/pcapi/app.py`), port `5001`.
- `api-data/apps/recommendation_v2` démarré en local (FastAPI), port `8801`
  (voir `RECOMMENDATION_API_URL` dans `pass-culture-main/api/.env.local.secret`).
- Connexion DB applicative locale opérationnelle (`pass-culture-main/api`, ports 5434/5433).
- Connexion DB recommendation_v2 (remote/staging via tunnel SSH, port 3307) si vous voulez
  tester l'appel HTTP complet. Note : un utilisateur fraîchement créé en local n'existe pas
  forcément dans la base `EnrichedUser` distante → `recoOrigin` peut rester `"unknown"`,
  c'est un comportement attendu, indépendant du bug QPI/GTL.

## 1. Seeder un utilisateur de test avec des réponses QPI réelles

**Important — schéma réel** : la colonne `answers` (JSON) de `UserCulturalSurvey` stocke chaque
réponse sous la forme `{"question_id": ..., "answer_ids": [...]}` (clé **`answer_ids`**, au
pluriel, confirmée par un export réel de la table). Le `UserCulturalSurveyFactory` utilisait à
tort la clé `answers_id` — bug corrigé (voir section "Points de vigilance").

`UserCulturalSurvey` expose désormais une vraie relation SQLAlchemy bidirectionnelle avec `User`
(`UserCulturalSurvey.user` / `User.culturalSurveys`, relation 1:1 via `uselist=False`, déclarée
dans `pcapi.core.cultural_survey.models` et `pcapi.core.users.models`, et enregistrée dans
`pcapi.models.install_models()`). Le `UserCulturalSurveyFactory` fonctionne donc directement avec
`user = factory.SubFactory(UserFactory)` — l'ancien contournement manuel via `flask shell`
(`TypeError: 'user' is an invalid keyword argument for UserCulturalSurvey`) n'est plus nécessaire.

```bash
cd pass-culture-main/api
source .venv/bin/activate
command flask shell <<'EOF'
from pcapi.core.cultural_survey.factories import UserCulturalSurveyFactory
from pcapi.core.users.models import User
from pcapi.models import db

user_id = 7  # qpi_test4@example.com
user = db.session.get(User, user_id)

# Exemple basé sur un enregistrement réel de la table (answer_ids, pas answers_id)
answers = [
    {"answer_ids": ["BIBLIOTHEQUE", "CINEMA", "CONCERT", "CONFERENCE", "COURS", "FESTIVAL"], "question_id": "SORTIES"},
    {"answer_ids": ["FESTIVAL_LIVRE", "FESTIVAL_CINEMA"], "question_id": "FESTIVALS"},
    {"answer_ids": [], "question_id": "SPECTACLES"},
    {"answer_ids": ["MATERIEL_ART_CREATIF", "PODCAST", "LIVRE", "JOUE_INSTRUMENT", "PRESSE_EN_LIGNE", "JEU_VIDEO", "FILM_DOMICILE"], "question_id": "ACTIVITES"},
    {"answer_ids": ["PROJECTION_CINEMA", "PROJECTION_VISITE", "PROJECTION_CD_VINYLE", "PROJECTION_FESTIVAL", "PROJECTION_LIVRE", "PROJECTION_CONFERENCE", "PROJECTION_JEU", "PROJECTION_ACTIVITE_ARTISTIQUE"], "question_id": "PROJECTIONS"},
    {"answer_ids": ["PHILOSOPHIE", "SOCIETE", "ROMANS"], "question_id": "LIVRES"},
    {"answer_ids": ["METAL", "FILMS", "CLASSIQUE", "RAP"], "question_id": "MUSIQUES"},
]

# `user.culturalSurveys` est la relation inverse ajoutée sur `User` (1:1, uselist=False)
row = user.culturalSurveys
if row:
    row.answers = answers
    db.session.commit()
else:
    row = UserCulturalSurveyFactory(user=user, answers=answers)

print("USER_ID:", row.userId)
for a in row.answers:
    print(a)
exit()
EOF
```

Alternative via le factory si vous voulez des réponses aléatoires plutôt qu'un jeu fixe :

```bash
cd pass-culture-main/api
source .venv/bin/activate
command flask shell <<'EOF'
from pcapi.core.users.factories import BeneficiaryGrant18Factory
from pcapi.core.cultural_survey.factories import UserCulturalSurveyFactory
from pcapi.core.cultural_survey.cultural_survey import SURVEY_QUESTIONS_AND_ANSWERS
from random import randrange
from factory.fuzzy import FuzzyChoice

user = BeneficiaryGrant18Factory(email="qpi_test4@example.com")

# Force au moins 1 réponse par question (évite des MUSIQUES/LIVRES vides)
answers = []
for question, possible_answers in SURVEY_QUESTIONS_AND_ANSWERS:
    n = randrange(len(possible_answers)) or 1
    answers.append({
        "question_id": question.id.value,
        "answer_ids": [FuzzyChoice(possible_answers).fuzz().id.value for _ in range(n)],
    })

survey = UserCulturalSurveyFactory(user=user, answers=answers)

print("USER_ID:", user.id, "EMAIL:", user.email)
for a in survey.answers:
    print(a)
exit()
EOF
```

Le mot de passe par défaut des factories de test est `settings.TEST_DEFAULT_PASSWORD`
(actuellement `user@AZERTY123`).

**Utilisateur de test déjà seedé localement (reproductible tant que la DB locale n'est pas
réinitialisée) :**

| Email | Password | User ID |
|---|---|---|
| `qpi_test4@example.com` | `user@AZERTY123` | `7` |

Réponses actuellement seedées pour cet utilisateur (basées sur un enregistrement réel) :

```text
{'answer_ids': ['PHILOSOPHIE', 'SOCIETE', 'ROMANS'], 'question_id': 'LIVRES'}
{'answer_ids': ['METAL', 'FILMS', 'CLASSIQUE', 'RAP'], 'question_id': 'MUSIQUES'}
```

### Vérifier les surveys existants / filtrer sur MUSIQUES-LIVRES

```bash
cd pass-culture-main/api
source .venv/bin/activate
command flask shell <<'EOF'
from pcapi.core.cultural_survey.models import UserCulturalSurvey
from pcapi.models import db

rows = db.session.query(UserCulturalSurvey).all()
print(f"TOTAL_SURVEYS: {len(rows)}")
for row in rows:
    matching = [a for a in row.answers if a.get("question_id") in ("MUSIQUES", "LIVRES")]
    print(f"user_id={row.userId} matching_count={len(matching)} matching={matching}")
exit()
EOF
```

## 2. Obtenir un access token JWT

```bash
curl -s -X POST http://localhost:5001/native/v1/signin \
  -H "Content-Type: application/json" \
  -d '{"identifier": "qpi_test4@example.com", "password": "user@AZERTY123"}' \
  | python3 -m json.tool
```

Récupérer le champ `accessToken` de la réponse (durée de vie courte, ~15 min — regénérer
si le test échoue avec un 401).

## 3. Tester l'endpoint playlist avec `isQpi: true`

Via `curl` :

```bash
TOKEN="<accessToken obtenu à l'étape 2>"

curl -s -X POST "http://localhost:5001/native/v1/recommendation/playlist" \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"isQpi": true}' | python3 -m json.tool
```

Via Swagger (`/native/v1/` docs) :
1. Cliquer sur **Authorize**, entrer `Bearer <accessToken>`.
2. Appeler `POST /native/v1/recommendation/playlist` avec le body `{"isQpi": true}`.

### Vérifier les logs

- Côté `pass-culture-main/api` (terminal Flask) : chercher le log
  `"Fetched cultural survey for QPI playlist"` → confirme que `qpi_answers` est bien
  récupéré depuis la DB et transmis dans le `body` (pas dans `params`, cf. bug historique).
- Côté `recommendation_v2` (terminal FastAPI) : chercher le log
  `"🧩 QPI context resolved into Titelive GTL labels."` → doit contenir :
  - `qpi_record` : la liste brute des réponses QPI envoyées par le client.
  - `backend_names` : uniquement les `answer_ids` des questions `MUSIQUES`/`LIVRES`,
    aplatis en une liste de strings (pas de liste de listes).
  - `gtl_labels` : les labels GTL Titelive résolus (non vide si `backend_names` contient
    des valeurs connues dans `qpi_gtl_mapping_mv`).

## 4. Tester la résolution GTL en isolation (sans passer par HTTP/Flask)

Utile pour valider `resolve_gtl_labels_from_backend_names` indépendamment de
l'authentification ou de la synchronisation `EnrichedUser` :

```bash
cd api-data/apps/recommendation_v2
source .venv/bin/activate
PYTHONPATH=src python3 - <<'EOF'
import asyncio
from services.db import AsyncSessionFactory
from core.qpi import resolve_gtl_labels_from_backend_names

async def main():
    async with AsyncSessionFactory() as db:
        backend_names = ["THRILLER", "CLASSIQUE", "FILMS", "MUSIQUES_AUCUN"]
        labels = await resolve_gtl_labels_from_backend_names(db, backend_names)
        print("INPUT:", backend_names)
        print("RESOLVED_GTL_LABELS:", labels)

asyncio.run(main())
EOF
```

Résultat attendu (exemple avec le jeu de `backend_names` ci-dessus) :

```text
INPUT: ['THRILLER', 'CLASSIQUE', 'FILMS', 'MUSIQUES_AUCUN']
RESOLVED_GTL_LABELS: ['Messes / Requiems / Passions', 'Musique Classique', 'Policier', 'Thriller',
'Musique de Films', 'Musique ancienne', 'Opéra / Opérette / Chant lyrique',
'Comédies musicales / Spectacles', 'Musique baroque']
```

## Points de vigilance / bugs corrigés

- **Clé réelle `answer_ids` vs `answers_id`** : la colonne `answers` en base utilise la clé
  `answer_ids` (confirmé par un export réel de `UserCulturalSurvey`). Le code (factory
  `UserCulturalSurveyFactory`, extraction `backend_names` dans
  `pipeline_playlist_recommendation.py`, fixture `utils/qpi_record.py`) utilisait à tort
  `answers_id` — ce qui aurait provoqué un `KeyError` silencieusement masqué ou une
  résolution GTL toujours vide en production. Corrigé partout pour utiliser `answer_ids`.
- `is_qpi` / `qpi_answers` doivent être lus/écrits sur `body` (`PlaylistRequestBody`), pas sur
  `params` (`PlaylistRequestQuery`) côté `pass-culture-main/api/src/pcapi/routes/native/v1/recommendation.py`.
  Sinon les valeurs ne sont jamais transmises à `recommendation_v2` (qui lit le JSON body via
  `Body(...)`).
- Le type `qpi_answers` doit être `list[dict[str, str | list[str]]]` (et non
  `list[dict[str, str]]`) des deux côtés (`PlaylistRequestBody` dans pcapi et
  `PlaylistRequestParams` dans recommendation_v2), car `answer_ids` est une liste. Un mauvais
  typage provoque un `422 Unprocessable Content`.
- Dans `pipeline_playlist_recommendation.py`, `backend_names` doit :
  1. filtrer les réponses sur `question_id in ("MUSIQUES", "LIVRES")` uniquement ;
  2. aplatir les `answer_ids` (qui sont des listes) en une seule `list[str]` — ne pas laisser
     une liste de listes, ce qui casse silencieusement le filtre SQL `.in_()` de
     `resolve_gtl_labels_from_backend_names`.
- Le fallback `QPI_RECORD`/`GTL_LABELS` (`utils/qpi_record.py`) est un jeu de données factice
  utilisé quand `params.qpi_answers` est vide — à garder uniquement comme filet de sécurité
  en dev, pas en production.
- **Relation `User` ↔ `UserCulturalSurvey`** : une relation SQLAlchemy bidirectionnelle 1:1 a
  été ajoutée (`UserCulturalSurvey.user` / `User.culturalSurveys`, `uselist=False` des deux
  côtés). Elle nécessite que le module `pcapi.core.cultural_survey.models` soit enregistré dans
  `pcapi.models.install_models()` — sinon SQLAlchemy échoue à la configuration des mappers avec
  `InvalidRequestError: ... failed to locate a name ("name 'UserCulturalSurvey' is not
  defined")` au démarrage de l'app ou dans `flask shell`. Grâce à cette relation,
  `UserCulturalSurveyFactory` n'a plus besoin de contournement : `user =
  factory.SubFactory(UserFactory)` fonctionne tel quel.
