---
name: reco-api-v2-ab-test
description: >
  Audit or annotate an ongoing or upcoming A/B test on the Recommendation API V2
  (apps/recommendation_v2). Checks cache isolation, BigQuery traceability,
  the presence and quality of HACK for AB testing blocks, and can generate or improve
  these blocks from a natural-language business description.
---

# Skill — Recommendation API V2: A/B Test Audit & Annotation

This skill applies **exclusively** to the `apps/recommendation_v2` project in the `api-data` repository.
It covers two usage modes described below.

For the complete reference on the A/B testing strategy, read:
`apps/recommendation_v2/docs/ab_testing.md`

---

## Mode 1 — A/B Test Audit

### When to use

- Before merging an A/B test branch onto the baseline.
- To verify that a test currently in production is properly instrumented.
- After an incident or doubt about the validity of results.

### Steps

#### Step 1 — Check branch naming (CI/CD)

```bash
git rev-parse --abbrev-ref HEAD
# The branch MUST start with "ab-test" (e.g. ab-test-71-graph-music)
# Otherwise the deployment to production will be blocked by CI/CD.
```

> 🔴 **BLOCKER**: branch not matching the `ab-test*` pattern → deployment impossible.

---

#### Step 2 — Check the common code base (branch divergence)

```bash
git fetch origin
# Commits present in main but ABSENT from the variant branch:
git --no-pager log origin/main ^HEAD --oneline
```

> ⚠️ **CRITICAL WARNING**: if this list is not empty, commits from the baseline are
> missing in the variant. This is not strictly a blocker, but must be explicitly reported
> in the audit with a justification. An unjustified divergence can invalidate the
> comparability of A/B groups regardless of the model being tested.
>
> Rule: no commit present in the baseline branch (A) should be absent from the variant branch (B).

---

#### Step 3 — Locate the tagged variant code

```bash
grep -rn "# --- HACK for AB testing ---" apps/recommendation_v2/src/
```

> 🔴 **BLOCKER**: if variant code is detected in the diff **without** these tags,
> the test does not comply with the convention and cannot be launched in production.
> Any code that differs between variants **must** be wrapped in:
> ```
> # --- HACK for AB testing ---
> ...
> # --- End of HACK for AB testing ---
> ```

---

#### Step 4 — Analyze the full diff for divergences outside HACK blocks

Read the full diff and look for logic differences **outside** tagged blocks:

```bash
git --no-pager diff origin/main...HEAD -- apps/recommendation_v2/src/
```

Typical divergences to detect:

| Type of divergence | Risk |
|---|---|
| Fallback condition modified outside HACK | 🟠 Asymmetric behavior on edge cases |
| Diversification parameter modified outside HACK | 🟠 Bias in result distribution |
| Threshold or priority order modified outside HACK | 🟠 Non-homogeneous comparison |
| Import or dependency added without tagging | 🟡 To be documented |

**Concrete example from the `ab_test_music_graph` A/B test:**

```python
# Baseline — Fallback limited to the coreservation model
is_coreservation_model = retrieval_model == SimilarOfferModelChoices.coreservation
if is_coreservation_model and len(final_similar_offers) == 0:
    # → the graph group received an empty response on zero-result cases

# Variant — Fallback extended to all models (intentional, not tagged)
# "Without this, the two A/B test groups would behave asymmetrically on zero-result cases..."
if len(final_similar_offers) == 0:
    # → both groups receive a fallback, fair comparison
```

This difference was intentional and documented in the comment, but outside a
`HACK` block. The audit must detect it, flag it, and verify it is justified.

> 🟠 Any difference outside a `HACK` block must be explained in the report.
> If intentional, suggest wrapping it in a `HACK` block with a comment.

---

#### Step 5 — Check the quality of the `# --- HACK for AB testing ---` block

For each block found, verify that the comment contains:

| Required element | Question to ask |
|---|---|
| **Business context** | What feature is being tested? On which playlist? For which offer/user type? |
| **What the variant changes** | Which parameters are modified? Which model is substituted? |
| **Trigger condition** | Is the `if` condition commented? Sufficiently explicit? |
| **Edge case justifications** | Are non-obvious choices (e.g., exclusion of an enum) explained? |
| **Trigger log** | Is there a `logger.debug/info` with the `[A/B TEST]` prefix logging parameters before/after the swap? |

> 🟠 **IMPORTANT**: a block without a trigger log makes it impossible to verify
> in production that the hack activated correctly.

---

#### Step 6 — Check HTTP cache isolation

Read `apps/recommendation_v2/src/connectors/redis_api.py`.

Verify that `_ab_test_variant_label` is injected into `versioned_signature` in both methods:
- `fetch_cached_response`
- `store_endpoint_response`

```python
# This pattern must be present in both methods:
versioned_signature = {**request_signature_data, "_ab_test_variant_label": settings.AB_TEST_VARIANT_LABEL}
```

Verify that **no endpoint** (`apps/recommendation_v2/src/api/*.py`) has manually added
`ab_test_variant_label`, `ab_test`, or `api_variant` to its `request_signature_data`.

> 🔴 **BLOCKER**: if `_ab_test_variant_label` is absent from `redis_api.py`, the HTTP cache
> is not isolated between variants → risk of cross-variant cache poisoning (see post-mortem
> `ab_test_music_graph` in `apps/recommendation_v2/docs/ab_testing.md`).

---

#### Step 7 — Check `ab_test` in API responses

Read `apps/recommendation_v2/src/schemas/playlist_recommendation.py`.

Verify that `RecommendationMetadata` contains `ab_test: str | None = None`.

Verify that controllers (`apps/recommendation_v2/src/controllers/pipeline_*.py`)
pass `ab_test=settings.AB_TEST_VARIANT_LABEL` when constructing `RecommendationMetadata`.

> ⚠️ **Data contract**: never add new fields to `RecommendationMetadata`
> without coordinating with the backend. `ab_test` is the only intended channel for variants.

Verify that endpoints (`apps/recommendation_v2/src/api/*.py`) log `ab_test_variant_label`
in their incoming request log (`📥 Incoming … request.`).

---

#### Step 8 — Check BigQuery traceability

> 📌 `past_offer_context` is a **dbt** model based on `run_googleapis_com_stderr`
> (the BigQuery table fed by the GCP Log Sink from `tracking.py`).

Read `apps/recommendation_v2/src/schemas/tracking_payload.py` and verify:
- `TrackingRequestExtraData` contains `ab_test_variant_label: str`
- `TrackingLogPayload` contains `ab_test_variant_label: str`

Read `apps/recommendation_v2/src/core/tracking.py` and verify that `ab_test_variant_label=settings.AB_TEST_VARIANT_LABEL`
is passed to both schemas when instantiating them.

> 💡 **Reminder**: `ab_test_variant_label` groups multiple `cloud_revision_name` values under the same
> logical version. If a hotfix is deployed during the test, the `cloud_revision_name` changes
> but `ab_test_variant_label` remains stable. Both dimensions are useful:
> - `ab_test_variant_label` → compare A/B groups (`main` vs `ab71-graph-music`)
> - `cloud_revision_name` → fine-grained analysis by exact deployment

---

#### Step 9 — Evaluate the offer resolution cache — contextual decision

> This step is critical and specific to the content of the A/B test.

Read the comment of the `# --- HACK for AB testing ---` block and answer this question:

**Does the variant modify the venue resolution logic (selection of the closest physical
offer for a multi-venue item)?**

| Answer | Action |
|---|---|
| **No** — the test only changes the retrieval model or filters | ✅ Shared cache is correct. Document this choice in the `HACK` block. |
| **Yes** — the test modifies the venue selection criterion, search radius, or any logic in `src/core/offer_resolution.py` | 🔴 Isolate. Add `settings.AB_TEST_VARIANT_LABEL` to `build_offer_resolution_cache_key`. Document in the `HACK` block. |
| **Uncertain** | 🟠 Analyze `src/core/offer_resolution.py`. Ask the team before launching. |

> ⚠️ Isolating this cache doubles (or more) Redis memory consumption.
> Only isolate if strictly necessary.

---

#### Step 10 — Check Cloud Run configuration

```bash
gcloud run revisions list --service recommendation-api-v2 --region europe-west1
gcloud run revisions describe <revision-name> --region europe-west1 \
  --format="value(spec.containers[0].env)"
```

Verify that:
- The **baseline** revision has `AB_TEST_VARIANT_LABEL=main`
- The **variant** revision has `AB_TEST_VARIANT_LABEL=<short-test-name>` (e.g. `ab71-graph-music`, no `v2-`, no spaces)
- Both values are **different**

> 🔴 A variant revision with `AB_TEST_VARIANT_LABEL=main` silently invalidates the test:
> both variants share the same HTTP cache and BigQuery rows are indistinguishable.

Check in Cloud Run startup logs that `AB_TEST_VARIANT_LABEL` appears in the `🔧 API Configuration`
log with the correct value.

---

#### Step 11 — Post-launch BigQuery validation (J+1 minimum)

> 📖 **Full analysis standard**: comparison methodology, statistical interpretation
> and decision on next steps →
> **[apiReCo] How to compare two models via A/B testing, then make a decision on next steps**
> https://app.notion.com/p/passcultureapp/apiReCo-Comment-comparer-deux-mod-les-via-A-B-testing-puis-prendre-une-d-cision-sur-les-next-steps-2acef645ecca498ebcfd6b3baf200bed

Run this query to confirm that both variants appear in the sink:

```sql
SELECT
  JSON_EXTRACT_SCALAR(context_extra_data, '$.ab_test_variant_label') AS ab_test_variant_label,
  COUNT(*) AS row_count,
  MIN(date) AS first_seen,
  MAX(date) AS last_seen
FROM `<project>.<dataset>.past_offer_context`
WHERE DATE(date) >= '<test_start_date>'
GROUP BY ab_test_variant_label
ORDER BY row_count DESC
```

> 🔴 If only one variant appears → `AB_TEST_VARIANT_LABEL` is misconfigured on a revision.

---

### Audit Report

Produce a structured report:

```
## A/B Test Audit — Recommendation API V2 — <test name>

| Check | Status | Detail |
|---|---|---|
| Branch naming (ab-test*) | 🟢/🔴 | |
| Common code base (missing commits in variant) | 🟢/🟠/🔴 | |
| HACK block present and tagged | 🟢/🟠/🔴 | |
| Divergences outside HACK blocks | 🟢/🟠/🔴 | |
| HACK block comment quality | 🟢/🟠/🔴 | |
| [A/B TEST] trigger log | 🟢/🟠/🔴 | |
| HTTP cache isolated (_ab_test_variant_label in redis_api.py) | 🟢/🔴 | |
| ab_test in API response (RecommendationMetadata) | 🟢/🟠/🔴 | |
| ab_test_variant_label in BigQuery sink | 🟢/🟠/🔴 | |
| Resolution cache — decision documented | 🟢/🟠/🔴 | |
| AB_TEST_VARIANT_LABEL Cloud Run verified | 🟢/🟠/🔴 | |

**Overall risk: LOW / MEDIUM / HIGH**

### 🔴 Blockers
### 🟠 Important points
### 🟡 Improvement suggestions
```

---

## Mode 2 — Annotating a HACK for AB testing block

### When to use

- Generate a `# --- HACK for AB testing ---` block **from scratch** based on a natural-language
  test description.
- Improve an existing block judged insufficiently explicit or incomplete.

### Expected input

The user provides a test description including:
- The targeted feature (endpoint, playlist, offer type)
- What the variant changes compared to the baseline (model, filters, parameters)
- The trigger condition (how to identify a group B request)
- Known edge cases (excluded enums, specific business rules, etc.)

### Process

#### 1. Read the code around the insertion point

Read the relevant pipeline file:
- `apps/recommendation_v2/src/controllers/pipeline_similar_offer.py`
- `apps/recommendation_v2/src/controllers/pipeline_playlist_recommendation.py`

To understand: available variables, log style, imported enums and models.

#### 2. Generate the block

```python
# --- HACK for AB testing ---
# Context: <clear business context, in English, 2-4 sentences describing the tested feature,
#           on which playlist, for which offer/user type>
#
# This AB test <description of what the variant changes and why this technical choice>.
#
# Trigger condition: <explicit explanation of the if condition — which inputs are intercepted
#                    and why this combination is specific to the target case>
#
# <Justification for any non-obvious edge case, e.g. why an enum is excluded>
<CONDITION_IF>:
    logger.debug(
        "⚠️ 🧪 [A/B TEST] AB test hack triggered: => <short description of the swap>",
        extra={
            "call_id": call_id,
            "original_<param>": <value_before>,
            "new_<param>": <value_after>,
        },
    )
    <param> = <new_value>
# --- End of HACK for AB testing ---
```

#### 3. Post-generation checks

- The log contains `[A/B TEST]` in the message
- All mutated parameters are logged both before **and** after the swap
- The condition is specific enough not to activate accidentally
- No premature `return` (unless intentional and documented)
- The block is placed **before** the pipeline phase that uses the mutated parameters

---

## Canonical example of a well-annotated HACK block

Taken from branch `ab-test-71-graph-recommendation-for-similar-offers-on-music`:

```python
# --- HACK for AB testing ---
# Context: On an offer page, two playlists are displayed:
#   - Playlist 1 "Dans la même catégorie": shows offers from the *same* search_group_name as the current offer.
#   - Playlist 2 "Ca peut aussi te plaire": shows offers from *all other* search_group_names
#     (excluding the current offer's search_group_name).
#
# This AB test targets Playlist 2 for music offers (search_group_name = MUSIQUE).
# When the frontend requests "Ca peut aussi te plaire" for a MUSIQUE offer, it sends all search_group_names
# *except* MUSIQUE (and NONE — see below). We intercept this specific request and swap:
#   - the search_group_names back to [MUSIQUE]
#   - the retrieval model to 'graph' (Knowledge Graph based on music metadata)
# This allows us to A/B test the graph-based recommendation strategy vs. the standard coreservation model
# on the "Ca peut aussi te plaire" playlist for music, for 50% of users over one month.
#
# Why exclude SearchGroupNameEnum.NONE?
# NONE is a special placeholder for offers that have not been assigned a proper search_group_name.
# It is not a real content category. When building Playlist 2 ("Ca peut aussi te plaire"), the frontend
# excludes the current offer's search_group_name to avoid showing offers from the same category.
# However, NONE is always excluded from this exclusion logic — because filtering *out* NONE would
# mistakenly remove uncategorised offers that are still valid recommendations.
# In short: NONE is never treated as a "real" category to match or exclude against.
SECOND_MUSIQUE_PLAYLIST_SEARCH_GROUPS = set(SearchGroupNameEnum) - {
    SearchGroupNameEnum.MUSIQUE,
    SearchGroupNameEnum.NONE,  # NONE is not a real category — always excluded from playlist filtering logic
}
if (
    search_group_names is not None
    and set(search_group_names) == SECOND_MUSIQUE_PLAYLIST_SEARCH_GROUPS
    and retrieval_model == SimilarOfferModelChoices.coreservation
):
    logger.debug(
        "⚠️ 🧪 [A/B TEST] AB test hack triggered: => replacing "
        "search_group_names with ['MUSIQUE'] "
        "and forcing retrieval_model to 'graph'.",
        extra={
            "call_id": call_id,
            "playlist": "Ca peut aussi te plaire",
            "original_search_group_names": [s.value for s in search_group_names],
            "original_retrieval_model": retrieval_model.value,
            "new_search_group_names": [SearchGroupNameEnum.MUSIQUE.value],
            "new_retrieval_model": SimilarOfferModelChoices.graph.value,
        },
    )
    search_group_names = [SearchGroupNameEnum.MUSIQUE]
    retrieval_model = SimilarOfferModelChoices.graph
# --- End of HACK for AB testing ---
```

---

## References

- Complete A/B testing guide: `apps/recommendation_v2/docs/ab_testing.md`
- Cache strategies: `apps/recommendation_v2/docs/cache_strategies.md`
- HTTP cache isolation: `apps/recommendation_v2/src/connectors/redis_api.py`
- BigQuery tracking: `apps/recommendation_v2/src/core/tracking.py`
- API response data contract: `apps/recommendation_v2/src/schemas/playlist_recommendation.py`
- Canonical HACK block example: branch `ab-test-71-graph-recommendation-for-similar-offers-on-music`,
  file `apps/recommendation_v2/src/controllers/pipeline_similar_offer.py`
