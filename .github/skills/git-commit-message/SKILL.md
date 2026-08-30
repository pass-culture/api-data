---
name: git-commit-message
description: 'Generates a properly formatted commit message from staged git diffs; use it whenever the user asks to write, generate, or suggest a commit message.'
---

## Goal

Read the staged diff and produce a commit message that matches the project's commit convention.

---

## Step 1 — Read the diff

Run the following command to get the staged diff (never omit `--no-pager`):

```bash
git --no-pager diff --staged
```

If nothing is staged, fall back to the full working-tree diff:

```bash
git --no-pager diff
```

---

## Step 2 — Determine the message body format

| Situation | Format |
|-----------|--------|
| Few changes (1–3 files, small diff) | Single line / single sentence after the header |
| Many changes (4+ files or large diff) | Bullet points, one per logical change, each line starting with `- ` (a hyphen followed by a space — never use `•` or any other bullet character) |

If a change involves a **complex implementation** (e.g. a multi-step algorithm, a non-trivial refactor, a migration), enumerate its sub-steps **indented with two spaces** under the parent bullet so they are visually distinct from top-level changes:

```
- refactor the geo resolution pipeline
  1. extract is_geolocated guard before the timed block
  2. add early-return log when GPS context is missing
  3. update downstream caller to branch on geolocated flag
```

---

## Step 3 — Build the commit header

The header **must** match this regex exactly:

```
^\((DA|DE|AE|DS|HF|BSR|PC)(-[0-9]+)?\) (build|lint|ci|docs|feat|fix|perf|refactor|test|core|dbt|chore)\(\w+\): \w+
```

### 3a — Ticket prefix

- If the user provides a ticket number (e.g. `DA-123`, `PC-42`), use it: `(DA-123)` or `(PC-42)`.
- Otherwise default to `(BSR)`.

### 3b — Commit type

Pick the most accurate type:

| Type | When to use |
|------|-------------|
| `feat` | New feature |
| `fix` | Bug fix |
| `refactor` | Code restructuring without behaviour change |
| `perf` | Performance improvement |
| `chore` | Maintenance, dependencies, tooling |
| `docs` | Documentation only |
| `test` | Tests only |
| `ci` | CI/CD pipeline |
| `build` | Build system |
| `lint` | Linting / formatting |
| `core` | Core business logic |
| `dbt` | dbt models |

### 3c — Scope

Use a short `snake_case` or `camelCase` word that identifies the affected module.

- If the changes are related to the `apps/fraud` project, use `compliance`.
- If the changes are related to the `apps/recommendation` project, use `reco_v1`.
- If the changes are related to the `apps/recommendation_v2` project, use `reco_v2`.

### 3d — Short description

- Write in **English**, imperative mood, lowercase after the colon.
- Be concise but descriptive.

---

## Step 4 — Assemble the final message

The body (bullet points) must be separated from the header by **exactly one blank line**.

**Short diff example (single line):**
```
(BSR) fix(reco_v2): move geo guard out of timed function to avoid measuring no-ops
```

**Large diff example (bullet points):**
```
(DA-57) refactor(reco_v2): extract geo guard and improve spatial resolution logging

- move is_geolocated check out of find_closest_offers_with_h3_index before the call
- add skip log when spatial DB resolution is bypassed due to missing GPS context
- add assert statements to satisfy type checker after guard removal
- update resolve_closest_venues_from_items to branch on geolocated state
```

**Large diff example with a complex sub-step:**
```
(PC-12) feat(reco_v2): add h3-based spatial retrieval with fallback to bounding box

- add h3_index field to Venue model and backfill migration
- implement find_closest_offers_with_h3_index as the primary retrieval path
  1. compute h3 cell from user GPS coordinates at resolution 8
  2. expand ring radius until minimum result threshold is reached
  3. fall back to bounding-box query when h3 grid returns no results
- wire new retrieval path into pipeline_playlist_recommendation controller
- add unit tests covering ring expansion and fallback behaviour
```

---

## Rules

- **Never** wrap the message in a code block when presenting it to the user — output it as plain text so it can be copied directly into a terminal or text editor (vim, emacs, etc.).
- Do **not** add a period at the end of the header line.
- The body (if any) is separated from the header by **one blank line**.
- Top-level bullet points use a plain hyphen-space (`- `) prefix — **never** `•`, `–`, `—`, or any Unicode bullet character.
- Sub-steps of a complex implementation are numbered (`  1.`, `  2.`, …) and indented with **two spaces** under their parent bullet.
- If unsure about the ticket number or type, ask the user before writing the message.
