# MLOps audit — what's worth doing now vs. later

> Companion to `refactor-audit-dashboard.md`. Read this before scheduling any
> ML/MLOps work — half the items on the unified checklist either don't apply
> (industrial / RL) or have lower ROI than they look. This document distinguishes.

## What's actually in the project today

The MLOps surface, as discovered by `grep` + reading `src/utils/ml_inference.py`
and `airflow/dags/ml_scoring_daily.py` :

| Asset | Location | State |
|---|---|---|
| Models (5 active) | `machine_learning/mlruns/{2,3,4,5,7}/models/*/artifacts/model.ubj` | XGBoost UBJ, paths hardcoded in `MODEL_PATHS` dict (`src/utils/ml_inference.py:30-36`) |
| MLflow tracking DB | `machine_learning/mlflow.db` | SQLite, 648 KB — runs metadata already there |
| Features | `FEATURE_COLUMNS` in `ml_inference.py:38` | 13 features, hardcoded list |
| Versioning | `MODEL_VERSION = "v1_noscaler"` | Single string constant, manual bump |
| Scoring DAG | `airflow/dags/ml_scoring_daily.py` | Runs daily, upserts `ml_song_predictions` |
| Debug DAG | `airflow/debug_dag/debug_ml_scoring.py` | Local exec mirror |
| Cache | `_model_cache` dict in `ml_inference.py:56` | In-process model cache |
| Prediction sink | `ml_song_predictions` table | Per-song predictions, joined with scoring inputs |

5 models, not 1 — my earlier "MLflow apporte rien" was wrong because I extrapolated from a checklist generality rather than reading the code. This audit corrects that.

## Recommendations — sorted by what I'd actually do

### #1 — Tests de non-régression ML — quick win, real value (1–2 h)

**What** : pytest fixture-based tests that feed `score_all_songs()` a frozen
10-row DataFrame and assert :

- output shape is `(10, N)` with the expected columns
- no NaN in `dw_probability`, `rr_probability`, `radio_probability`
- probabilities are in `[0, 1]`
- `forecast_streams_7d` is non-negative and finite
- a known-stable input row produces predictions within ±5% of a frozen baseline (catches silent model swaps)

**Why** : 5 models live in `MODEL_PATHS` as hardcoded paths. The day someone
swaps a UBJ artifact, or refactors `FEATURE_COLUMNS`, or pushes a new
`MODEL_VERSION`, the tests catch the regression at PR time — not at the next
Airflow run in prod.

**Cost** : 1–2 h. The fixture is a 10-row DataFrame committed to
`tests/fixtures/ml_scoring_input.csv` + a baseline `tests/fixtures/ml_scoring_baseline.json`.

**Risk** : low — read-only against models, no DB needed (mock or skip if models
absent in CI).

**Trigger** : do this **next time you touch a model or feature**. If you push a
new model artifact without these tests, you fly blind.

**Honest take** : I'd recommend doing this one if you have an hour. It's the
single MLOps item where the cost/benefit is clearly positive at this scale.

### #2 — Audit before drift detection — defer until you have a signal (4–6 h to implement)

**What the checklist says** (§9.3) : PSI / KS-test per feature on weekly cron,
alert when drift > 0.25.

**Why I'd wait** : drift detection has value only when (a) someone consumes the
signal and acts, or (b) it gates a retraining decision. Today there's neither —
retraining is manual and no operator watches a drift dashboard. Implementing
drift now produces a metric nobody looks at.

**When to revisit** : when one of the following happens, drift goes from "nice
to have" to "needed" :
- A prediction starts looking weird in `views/trigger_algo.py` and you want to know if it's the model or the input distribution.
- You add a 6th model and want to know if a new model's input space matches the training data of an existing one.
- You set up a `ml-promotion.yml` CI gate (per the ML checklist §9.5b) — drift becomes a precondition for promotion.

**Cost when triggered** : 4–6 h. The infra is well-defined (PSI baseline, KS
test, store per-feature daily snapshots in a `ml_feature_drift` table, surface
in a Streamlit view). The cost is in the *deciding what threshold matters* —
which is exactly the conversation that's missing today.

### #3 — MLflow model registry promotion — defer, but smaller delta than I said (2 h)

**Status** : MLflow tracking is **already in place** (`machine_learning/mlflow.db`
exists, 648 KB of metadata). What the checklist §9.1b calls out is the
**model registry** — naming + staging + promotion of models, vs the current
file-path-pinning in `MODEL_PATHS`.

**Why my earlier "MLflow apporte rien" was wrong** : I confused tracking
(present) with registry (absent). The registry would replace this :

    MODEL_PATHS = {
        "dw_classifier": "2/models/m-5487d6f842b84d099659332045aad1db/artifacts/model.ubj",
        ...
    }

with this :

    MODEL_NAMES = {
        "dw_classifier": "dw_classifier:Production",  # MLflow stage alias
        ...
    }

**Why still defer** : the current hardcoded paths *work*, are explicit, and
version-control friendly (a model bump = one diff line). The MLflow registry
shines when you have :
- multiple concurrent training runs from different people
- A/B testing of model versions
- a need to atomically roll back a model

None of those are open today. The registry is a 2 h refactor that buys you
flexibility you don't need yet.

**When to revisit** : if you (a) start training new models more than ~1×/month,
or (b) want to A/B test two `dw_classifier` versions in shadow.

### #4 — Auto-retraining — keep manual (no work)

Checklist §9.4 says : automate retraining on drift. With manual scoring
triggered <1×/month and only 5 models, automating the retrain decision adds
complexity (cron, retraining DAG, evaluation gates, promotion script) for
behavior that already happens fine with `views/trigger_algo.py` button +
human review.

**Defer indefinitely.** Revisit only if retraining cadence becomes weekly+.

### #5 — Add `MODEL_VERSION` to prediction rows — **already in DB** (2026-05-14 correction)

**My initial claim** : that `MODEL_VERSION` was missing from `ml_song_predictions`
and needed a migration. **Wrong** — checked the live schema and the column is
already there, included in the UNIQUE constraint `(artist_id, song,
prediction_date, model_version)`, and `score_all_songs()` writes the current
`MODEL_VERSION` constant ("v1_noscaler") into each row.

**One minor inconsistency that's not worth fixing alone** : the column default
is `'v1'` (from when the constant was named differently), but the code writes
`'v1_noscaler'` explicitly. Since the explicit value always wins, the default
is dead. Drop it in migration 027 only if you happen to touch the table for
another reason.

Closing this item — no work needed on the DB or the inference code.

### #6 — Validation gates for `ml-promotion.yml` — checklist item §9.5b — defer

Hypothetical CI gate that blocks model promotion if F1 / AUC drops below
threshold. There's **no `ml-promotion.yml`** today and the promotion process
is "drop a UBJ file in `machine_learning/mlruns/`". Defer until a formal
promotion process exists.

## Suggested order if you do attack MLOps

| Rank | Item | Effort | Risk | When to trigger | Status |
|---|---|---|---|---|---|
| 1 | #1 tests de non-régression ML | 1–2 h | Low | Next time you touch a model or `FEATURE_COLUMNS` | **DONE 2026-05-14** (tests/test_ml_inference.py, 10 tests, baseline frozen) |
| 2 | #5 add `model_version` to predictions | — | — | — | **Already in DB schema** (see #5 above) |
| 3 | #3 MLflow registry migration | 2 h | Low | When >1 person trains models, or A/B testing needed | Open |
| 4 | #2 drift detection | 4–6 h | Low | When a weird prediction triggers a "why?" | Open |
| 5 | #6 promotion gates | 1–2 h | Low | When `ml-promotion.yml` is created | Open |
| 6 | #4 auto-retrain | — | — | Only if cadence becomes weekly+ | Defer indefinitely |

## Bug latents découverts en exécutant l'audit (2026-05-14)

Deux problèmes que personne n'avait flagués, surfacés par le test fixture
generation work :

### Bug 1 — sklearn missing in Airflow image (P2)

`Dockerfile.airflow` n'installait pas `scikit-learn`, qui est une dépendance
implicite de `xgboost>=2.x` (les méthodes `predict_proba`/`predict` lèvent
`RuntimeError: sklearn needs to be installed` sans). Le DAG
`ml_scoring_daily` chargeait les modèles avec succès apparent mais
échouait silencieusement à la prédiction — les `try/except` dans
`score_song` avalaient l'erreur et renvoyaient `None`.

**Impact** : `ml_song_predictions` n'a probablement pas reçu de prédictions
correctes depuis l'install initial. À vérifier avec
`SELECT MAX(prediction_date), COUNT(*) FROM ml_song_predictions GROUP BY model_version`.

**Fix livré 2026-05-14** : `scikit-learn>=1.3.0` ajouté dans `requirements.txt`
et `pyproject.toml`, `Dockerfile.airflow` étendu pour installer
`build-essential` + `libcairo2-dev` + `pkg-config` (nécessaires pour le source
build de `pycairo` via `rlpycairo` via `xhtml2pdf`). Images Airflow rebuildées.

### Bug 2 — Regressors produce constant forecasts (P3, model QA)

En appliquant `score_song()` sur 3 fixtures très différentes (fresh release,
established song, viral breakout), les régresseurs `dw_streams_forecast_7d`
et `rr_streams_forecast_7d` produisent **les mêmes valeurs** (7301 et 12
respectivement) pour les 3 inputs. Les classifiers, eux, discriminent
normalement.

**Hypothèses** :
- Les régresseurs ont été entraînés avec un input space différent de celui
  des fixtures (qui utilisent des valeurs synthétiques plausibles).
- Les régresseurs convergent en plateau pour les inputs hors-train-distribution.
- Les features critiques pour les régresseurs ne sont pas dans `FEATURE_COLUMNS`
  (`HowManySongsDoYouHaveInRadioRightNow` et `NonAlgoStreams28Days_log` sont
  toujours 0/0 en prod par défaut — peut-être ces deux dominent les régresseurs).

**Pas fixé ici** — ouvre une question de qualité modèle qui mérite une
brique de QA dédiée. Le test de non-régression actuel l'**accepte** comme
baseline (ce n'est pas un bug code, c'est une propriété du modèle).

## What I would NOT do, motivated

| Item | Why not |
|---|---|
| Adopt the whole §9.5c Prometheus + Grafana for ML | Rejected by ADR-002. The signal-to-cost ratio for a single-tenant scoring DAG isn't worth Grafana setup. |
| Migrate XGBoost UBJ artifacts to ONNX | Vendor neutrality has zero value here — XGBoost is the only model type, and it's not going anywhere. |
| Introduce DVC for data versioning | The training data is S4A CSVs + the model is XGBoost on tabular features. There's no audio file or image dataset to version. DVC would solve a problem we don't have. |
| Add `ml-nightly.yml` CI to retrain | Per #4 above. |

## How to use this file

- Before a Brick that touches ML : skim ranks 1–2 and decide if the brick should ship the test fixture or the version-column migration alongside.
- For a Brick unrelated to ML : ignore this file.
- If you observe a weird prediction in prod : jump to rank 4 (drift) and rank 1 (regression tests) — those will tell you whether the issue is input drift or a silent model swap.

## What changed between my earlier "pas pertinent" and this audit

I had claimed "<3 models, MLOps overhead > benefit, defer everything". After
reading the actual code I found 5 models, MLflow tracking already in place,
and a clear quick-win (regression tests + version-column). Two items I'd
defer no longer (#1 and #5 are now in the "do it next time you touch the
DAG" tier). The original framing held for drift detection, auto-retraining,
and full registry migration — those still wait for triggers that don't exist
yet.

The lesson : reading the code beats checklist-driven thinking. The MLOps
checklist is generic by design ; the project's actual ML setup is more
mature than a generic "1 model SaaS dashboard" would suggest.
