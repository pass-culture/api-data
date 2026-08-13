# Structuration d'une collection Bruno pour tester l'API de recommandation

## 1. Arborescence de la collection

```
bruno/
├── bruno.json
├── environments/
│   ├── local.bru
│   ├── staging.bru
│   └── prod.bru
├── 00-health/
│   └── ping.bru
├── 01-fallbacks/
│   ├── unknown-user.bru
│   ├── unknown-offer.bru
│   └── unknown-artist.bru
├── 02-latency/
│   ├── playlist-latency-warm.bru
│   └── playlist-latency-cold.bru
├── 03-filters/
│   ├── playlist-reco-filtre-genre.bru
│   ├── playlist-reco-filtre-multi.bru
│   └── playlist-reco-filtre-verif-respect.bru
├── 04-cold-start/
│   ├── user-cold.bru
│   └── user-warm.bru
├── 05-model-config/
│   └── force-config-check-logs.bru
├── 06-cache/
│   ├── 1-call-initial.bru
│   └── 2-call-cache-hit.bru
├── 07-geoloc/
│   ├── sans-geoloc.bru
│   ├── geoloc-zone-dense.bru
│   └── geoloc-zone-sparse.bru
└── 08-similar-offers-artists/
    ├── similar-offers-ok.bru
    ├── similar-offers-unknown.bru
    ├── similar-artists-ok.bru
    └── similar-artists-unknown.bru
```

Chaque dossier = un dossier Bruno (clic droit > New Folder), chaque fichier = une requête. L'ordre `seq` dans les fichiers garantit l'exécution dans l'ordre voulu quand tu lances tout le dossier via le Runner (utile pour le test de cache notamment).

## 2. Environnements

`environments/local.bru` (idem pour staging/prod avec les bonnes valeurs) :

```
vars {
  base_url: http://localhost:8000
  auth_token: {{process.env.API_TOKEN}}

  # Utilisateurs de test à seed en base au préalable
  user_warm: usr_test_warm_001
  user_cold: usr_test_cold_001
  user_unknown: usr_does_not_exist

  offer_unknown: off_does_not_exist
  artist_unknown: art_does_not_exist

  offer_warm: off_test_warm_001
  artist_warm: art_test_warm_001

  forced_model_config: model_v2_experimental

  geo_ip_dense: 8.8.8.8
  geo_ip_sparse: 41.203.15.1
}
```

Les valeurs `user_warm` / `user_cold` supposent que tu as un **script de seed** (SQL ou endpoint admin) qui crée ces comptes avec un historique riche (warm) ou vide (cold) avant de lancer la suite. Ce n'est pas géré par Bruno lui-même — à faire tourner en amont dans la CI (voir §7).

## 3. Fallbacks (user/offer/artist inconnus)

`01-fallbacks/unknown-user.bru` :

```
meta {
  name: Fallback - user inconnu
  type: http
  seq: 1
}

get {
  url: {{base_url}}/recommendations/playlist?user_id={{user_unknown}}
  body: none
  auth: bearer
}

auth:bearer {
  token: {{auth_token}}
}

tests {
  test("status attendu documenté (200 fallback ou 404)", function() {
    expect(res.status).to.be.oneOf([200, 404]);
  });

  test("si 200, le contrat de fallback est respecté", function() {
    if (res.status === 200) {
      expect(res.body).to.have.property("tracks");
      expect(res.body.fallback_reason).to.exist; // à adapter au champ réel
    }
  });
}
```

Duplique ce fichier pour `unknown-offer.bru` et `unknown-artist.bru` en changeant juste l'URL et le paramètre. L'idée clé : **documenter le contrat** dans le test lui-même (200 vide vs 404), pas juste vérifier "ça ne plante pas".

## 4. Longueur de playlist

Ajoute dans `01-fallbacks` ou un dossier dédié un test générique de longueur :

```
tests {
  test("playlist a la longueur attendue", function() {
    expect(res.body.tracks.length).to.be.at.least(1);
    expect(res.body.tracks.length).to.be.at.most(50); // borne haute métier
  });
}
```

## 5. Latence

`02-latence/playlist-latency-warm.bru` :

```
get {
  url: {{base_url}}/recommendations/playlist?user_id={{user_warm}}
}

tests {
  test("latence sous le seuil (warm)", function() {
    expect(res.responseTime).to.be.below(300); // ms, seuil à ajuster
  });
}
```

Duplique avec `user_cold` et un seuil plus haut (le cold start est censé être plus lent — documente le seuil différent explicitement).

Pour des stats agrégées (p95, p99), Bruno seul ne suffit pas bien — lance le dossier via `bru run --iteration-count 50` en CLI et exporte le JSON de résultats pour calculer les percentiles côté script externe (petit script Node/Python).

## 6. Filtres

`03-filtres/playlist-reco-filtre-genre.bru` :

```
get {
  url: {{base_url}}/recommendations/playlist?user_id={{user_warm}}&genre=jazz
}

tests {
  test("toutes les pistes respectent le filtre genre", function() {
    res.body.tracks.forEach(track => {
      expect(track.genre).to.equal("jazz");
    });
  });
}
```

Fais un fichier par combinaison de filtres importante (genre seul, genre+decade, exclusion d'artiste, etc.), et un fichier "multi-filtres" qui vérifie le cumul (AND logique). Le test générique est toujours le même pattern : boucler sur `res.body.tracks` et assert sur chaque item.

## 7. Cold start / Warm

`04-cold-start/user-cold.bru` :

```
get {
  url: {{base_url}}/recommendations/playlist?user_id={{user_cold}}
}

tests {
  test("réponse valide même sans historique", function() {
    expect(res.status).to.equal(200);
    expect(res.body.tracks.length).to.be.at.least(1);
  });

  test("stratégie de cold start indiquée", function() {
    expect(res.body.strategy).to.equal("cold_start"); // si exposé
  });
}
```

**Pré-requis** : les users `warm`/`cold` doivent exister en base avant le run. Deux options :
- un script de seed exécuté en étape CI avant `bru run` (ex: `psql -f seed_test_users.sql`)
- un endpoint admin `/test/seed` appelé en pré-requête de collection (`script:pre-request` au niveau du dossier)

## 8. Forcer une config modèle + vérifier les logs

`05-model-config/force-config-check-logs.bru` :

```
get {
  url: {{base_url}}/recommendations/playlist?user_id={{user_warm}}&model_config={{forced_model_config}}
  headers {
    X-Request-Id: {{request_id}}
  }
}

script:pre-request {
  bru.setVar("request_id", "test-" + Date.now());
}

tests {
  test("la réponse indique la config utilisée", function() {
    expect(res.body.model_used).to.equal(bru.getEnvVar("forced_model_config"));
  });
}
```

La vérif "dans les logs" ne peut pas se faire depuis Bruno seul. Deux approches :
1. **Idéal** : l'API renvoie le `model_used` dans la réponse (ce que fait le test ci-dessus) — évite d'aller chercher dans les logs.
2. Si tu dois vraiment checker les logs : génère un `X-Request-Id` unique par requête (comme ci-dessus), puis un script externe (post-run) interroge ton système de logs (Datadog/ELK/CloudWatch) avec ce request_id et vérifie que la config forcée y apparaît. Ça sort du scope Bruno — un petit script Node en `script:post-response` peut au mieux logger le request_id pour investigation manuelle, mais l'assertion automatique doit se faire côté log platform.

## 9. Cache

`06-cache/1-call-initial.bru` (seq: 1) :

```
meta { seq: 1 }

get {
  url: {{base_url}}/similar-offers?offer_id={{offer_warm}}
}

tests {
  test("premier appel n'est pas depuis le cache", function() {
    expect(res.body.from_cache).to.equal(false);
  });
}
```

`06-cache/2-call-cache-hit.bru` (seq: 2) :

```
meta { seq: 2 }

get {
  url: {{base_url}}/similar-offers?offer_id={{offer_warm}}
}

tests {
  test("second appel vient du cache", function() {
    expect(res.body.from_cache).to.equal(true);
  });

  test("le contenu est identique au premier appel", function() {
    expect(res.body.tracks).to.deep.equal(bru.getVar("first_call_tracks"));
  });
}
```

Pense à stocker `bru.setVar("first_call_tracks", res.body.tracks)` dans le `script:post-response` du fichier 1 pour pouvoir comparer dans le fichier 2. Lance ce dossier via le Runner (pas requête par requête à la main) pour garantir l'ordre.

## 10. Géolocalisation

`07-geoloc/sans-geoloc.bru` :

```
get {
  url: {{base_url}}/recommendations/playlist?user_id={{user_warm}}
}

tests {
  test("fonctionne sans geoloc, index par défaut utilisé", function() {
    expect(res.body.debug.geo_index).to.equal("default");
  });
}
```

`07-geoloc/geoloc-zone-dense.bru` :

```
get {
  url: {{base_url}}/recommendations/playlist?user_id={{user_warm}}
  headers {
    X-Forwarded-For: {{geo_ip_dense}}
  }
}

tests {
  test("index géo dense correctement sélectionné", function() {
    expect(res.body.debug.geo_index).to.equal("dense-region-index");
  });
}
```

Duplique pour `geoloc-zone-sparse.bru`. Le point important : demande à l'équipe backend d'exposer un champ `debug.geo_index` (ou équivalent) dans la réponse en mode debug/staging — sans ça, impossible de vérifier "le bon index" depuis un test API pur.

## 11. Redis — persistance des clés entre déploiements

Ce n'est pas un test HTTP, donc ça sort de Bruno à proprement parler. Deux pistes :

- **Si l'API expose un endpoint debug** (`/debug/cache/keys?pattern=...`), tu peux faire un fichier Bruno classique qui appelle cet endpoint avant et après déploiement, et diff les deux réponses.
- **Sinon**, script externe à lancer en CI (hors Bruno) :
  ```bash
  # avant déploiement
  redis-cli --scan --pattern "similar:*" > keys_before.txt
  # déploiement...
  redis-cli --scan --pattern "similar:*" > keys_after.txt
  diff keys_before.txt keys_after.txt
  ```
  Documente ce script à côté de la collection Bruno (dossier `scripts/` au même niveau) pour que la CI l'exécute en plus des runs Bruno.

## 12. Similar offers / similar artists — cas inconnus

`08-similar-offers-artists/similar-offers-unknown.bru` :

```
get {
  url: {{base_url}}/similar-offers?offer_id={{offer_unknown}}
}

tests {
  test("contrat documenté: 200 vide OU 404", function() {
    expect(res.status).to.be.oneOf([200, 404]);
  });

  test("si 200, liste vide", function() {
    if (res.status === 200) {
      expect(res.body.tracks).to.be.an("array").that.is.empty;
    }
  });
}
```

Même pattern pour `similar-artists-unknown.bru`. Garde aussi un cas "ok" (`similar-offers-ok.bru`) avec un offer connu pour avoir le contraste nominal/erreur dans la même suite.

## 13. Détail — Script de seed (cold/warm)

Deux options selon ton contexte. Choisis celle qui colle à ton archi.

**Option A — SQL direct** (`scripts/seed_test_users.sql`) :

```sql
-- User warm : historique riche
INSERT INTO users (id, created_at) VALUES ('usr_test_warm_001', NOW() - INTERVAL '180 days')
  ON CONFLICT (id) DO NOTHING;

INSERT INTO listening_history (user_id, track_id, played_at)
SELECT 'usr_test_warm_001', track_id, NOW() - (random() * INTERVAL '90 days')
FROM tracks
ORDER BY random()
LIMIT 200
ON CONFLICT DO NOTHING;

-- User cold : existe mais sans historique
INSERT INTO users (id, created_at) VALUES ('usr_test_cold_001', NOW())
  ON CONFLICT (id) DO NOTHING;
DELETE FROM listening_history WHERE user_id = 'usr_test_cold_001';

-- Offer et artist de référence pour les tests warm
INSERT INTO offers (id, ...) VALUES ('off_test_warm_001', ...) ON CONFLICT (id) DO NOTHING;
INSERT INTO artists (id, ...) VALUES ('art_test_warm_001', ...) ON CONFLICT (id) DO NOTHING;
```

Exécution avant chaque run : `psql $DATABASE_URL -f scripts/seed_test_users.sql`

Idempotent (`ON CONFLICT DO NOTHING` + `DELETE` explicite pour le cold) pour pouvoir tourner à chaque run de CI sans erreur ni duplication.

**Option B — Endpoint admin** (si tu ne veux pas exposer un accès DB direct à la CI) :

Un endpoint `POST /internal/test-fixtures/reset` protégé par un token interne, appelé en amont via un `script:pre-request` au niveau du **dossier racine** de la collection Bruno (s'applique à tout run) :

```
script:pre-request {
  if (!bru.getVar("fixtures_seeded")) {
    await new Promise((resolve, reject) => {
      const req = require('http').request(
        bru.getEnvVar("base_url") + "/internal/test-fixtures/reset",
        { method: "POST", headers: { Authorization: "Bearer " + bru.getEnvVar("internal_token") } },
        (res) => resolve()
      );
      req.on("error", reject);
      req.end();
    });
    bru.setVar("fixtures_seeded", true);
  }
}
```

Recommandation : **Option A en CI** (plus rapide, pas de dépendance à un endpoint interne à maintenir), **Option B en local** pour les devs qui n'ont pas d'accès direct à la base de staging.

## 14. Détail — Post-traitement latence (p95/p99)

`bru run` produit un JSON avec `res.responseTime` par requête. Petit script Node (`scripts/analyze-latency.js`) à lancer après le run :

```javascript
const fs = require("fs");

const results = JSON.parse(fs.readFileSync(process.argv[2] || "results.json", "utf-8"));

function percentile(arr, p) {
  const sorted = [...arr].sort((a, b) => a - b);
  const idx = Math.ceil((p / 100) * sorted.length) - 1;
  return sorted[Math.max(0, idx)];
}

const timings = results.results
  .filter(r => r.request.url.includes("/recommendations/playlist"))
  .map(r => r.response.responseTime);

const p50 = percentile(timings, 50);
const p95 = percentile(timings, 95);
const p99 = percentile(timings, 99);

console.log(`p50: ${p50}ms | p95: ${p95}ms | p99: ${p99}ms`);

const THRESHOLD_P95 = 300;
if (p95 > THRESHOLD_P95) {
  console.error(`ÉCHEC: p95 (${p95}ms) dépasse le seuil (${THRESHOLD_P95}ms)`);
  process.exit(1);
}
```

Pour un échantillon statistiquement utile, lance la requête plusieurs fois via l'option de répétition du CLI :

```bash
bru run 02-latence --env staging --iteration-count 50 --reporter-json results.json
node scripts/analyze-latency.js results.json
```

## 15. Détail — Pipeline CI (exemple GitHub Actions)

`.github/workflows/api-tests.yml` :

```yaml
name: API Tests (Bruno)

on:
  pull_request:
  workflow_dispatch:

jobs:
  bruno-tests:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4

      - name: Setup Node
        uses: actions/setup-node@v4
        with:
          node-version: "20"

      - name: Install Bruno CLI
        run: npm install -g @usebruno/cli

      - name: Seed test fixtures
        run: psql ${{ secrets.STAGING_DATABASE_URL }} -f scripts/seed_test_users.sql

      - name: Snapshot Redis keys (before)
        run: redis-cli -u ${{ secrets.STAGING_REDIS_URL }} --scan --pattern "similar:*" > keys_before.txt

      - name: Run functional + fallback + filter tests
        run: bru run api-tests/01-fallbacks api-tests/03-filtres api-tests/04-cold-start api-tests/08-similar-offers-artists --env staging --reporter-json results-functional.json

      - name: Run cache tests (ordre garanti)
        run: bru run api-tests/06-cache --env staging --reporter-json results-cache.json

      - name: Run latency tests (50 itérations)
        run: bru run api-tests/02-latence --env staging --iteration-count 50 --reporter-json results-latency.json

      - name: Analyze latency (p95/p99)
        run: node scripts/analyze-latency.js results-latency.json

      - name: Snapshot Redis keys (after) + diff
        run: |
          redis-cli -u ${{ secrets.STAGING_REDIS_URL }} --scan --pattern "similar:*" > keys_after.txt
          diff keys_before.txt keys_after.txt || (echo "Clés Redis perdues/modifiées entre déploiements" && exit 1)

      - name: Upload results
        if: always()
        uses: actions/upload-artifact@v4
        with:
          name: bruno-results
          path: results-*.json
```

Les tests géoloc et model-config (dossiers 05 et 07) sont volontairement exclus de ce run standard tant que les champs `debug.geo_index` / `model_used` ne sont pas exposés par l'API — à ajouter dès qu'ils le sont (voir plan ci-dessous).

## 16. Plan d'implémentation

**Phase 0 — Socle (0.5 à 1 jour)**
- Créer la collection Bruno (`bruno init`), les 3 environnements, committer la structure de dossiers.
- Écrire et tester `seed_test_users.sql` en local.
- Valider avec le backend le contrat 200-vide vs 404 pour les cas inconnus (bloquant : sans ça, la moitié des tests fallback ne peut pas s'écrire correctement).

*Dépendance : accès à une base de staging + un backend qui valide/fige les contrats d'erreur.*

**Phase 1 — Tests fonctionnels de base (1 à 2 jours)**
- Fallbacks (user/offer/artist inconnus), longueur de playlist — dossier 01
- Filtres (genre, multi-filtres, vérif de respect) — dossier 03
- Similar offers/artists (ok + unknown) — dossier 08

*Aucune dépendance externe autre que le contrat d'erreur figé en Phase 0. Plus fort ROI immédiat — à livrer en premier.*

**Phase 2 — Cold start & cache (1 jour)**
- Seed des users warm/cold en base (script Phase 0 exécuté en pré-run)
- Dossier 04 (cold-start), dossier 06 (cache)

*Dépendance : champ `from_cache` exposé par l'API — à vérifier/demander dès maintenant si pas déjà fait.*

**Phase 3 — Latence + post-traitement (1 jour)**
- Dossier 02 (latence warm/cold), script `analyze-latency.js`
- Définir les seuils p95/p99 avec l'équipe (placeholders à 300ms — à valider avec de la donnée réelle de prod si dispo).

*Pas de dépendance API, juste un besoin d'alignement sur les seuils acceptables.*

**Phase 4 — Champs debug côté API (à paralléliser tôt)**
- Demander l'exposition de `model_used`, `debug.geo_index`, `strategy` (cold_start) en staging/debug.
- Peut démarrer **dès la Phase 0** en parallèle (ticket backend) pour ne pas bloquer les phases suivantes.

**Phase 5 — Model config + Geoloc (0.5 à 1 jour, une fois Phase 4 livrée)**
- Dossier 05 (force-config), dossier 07 (geoloc sans/avec, zones dense/sparse)

**Phase 6 — Redis persistence (0.5 jour)**
- Script `keys_before.txt` / `keys_after.txt` + diff, intégré dans le pipeline de déploiement (pas seulement la CI de PR — idéalement un job autour de chaque déploiement staging/prod).

**Phase 7 — Intégration CI (0.5 à 1 jour)**
- Workflow tel que détaillé en §15. Secrets à configurer : `STAGING_DATABASE_URL`, `STAGING_REDIS_URL`, `API_TOKEN`.
- Décider du déclencheur : sur chaque PR (sous-ensemble rapide : fallbacks + filtres) vs nightly (suite complète, latence 50 itérations + Redis diff autour du déploiement).

**Estimation totale** : ~5 à 7 jours de travail effectif, dont 1 à 2 jours dépendent du backend (champs debug) et peuvent tourner en parallèle du reste dès le jour 1.

**Ordre recommandé si tu dois prioriser** : Phase 0 → Phase 1 (valeur immédiate, zéro dépendance) → Phase 2 → Phase 3, pendant que la Phase 4 tourne en tâche de fond côté backend → Phase 5 dès que possible → Phases 6 et 7 en fin de cycle pour industrialiser.

## Résumé des prérequis côté API (à demander au besoin)
- Champ `from_cache` dans les réponses de similar-offers/artists
- Champ `model_used` (ou équivalent) dans la réponse de recommandation
- Champ `debug.geo_index` en mode debug/staging
- Champ `strategy` ou équivalent pour distinguer cold start
- Contrat clair et stable pour les 404 vs 200-vide (à figer avec le back une bonne fois pour toutes, puis à tester)
