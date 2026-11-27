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
  tester l'appel HTTP complet.

## 1. Seeder un utilisateur de test avec des réponses QPI réelles


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

- Côté `recommendation_v2` (terminal FastAPI) : chercher le log
  `"🧩 QPI context resolved into Titelive GTL labels."` → doit contenir :
  - `qpi_record` : la liste brute des réponses QPI envoyées par le client.
  - `backend_names` : uniquement les `answer_ids` des questions `MUSIQUES`/`LIVRES`,
    aplatis en une liste de strings (pas de liste de listes).
  - `gtl_labels` : les labels GTL Titelive résolus (non vide si `backend_names` contient
    des valeurs connues dans `qpi_gtl_mapping_mv`).

