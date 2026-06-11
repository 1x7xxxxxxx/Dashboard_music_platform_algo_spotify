# ML methodology comparison — your notebook/`train.py` vs an independent re-derivation

**Date:** 2026-06-05 · **Data:** `01_data/data_anon.csv` (508 rows, 352 distinct songs)
**Baseline:** `machine_learning/train.py` → `models/v2_noscaler/` (your work)
**Challenger:** `machine_learning/analysis/{01..04}_*.py` → `models/v3/` (independent)

This is a *learning* document first. The reproducible scripts are in
`machine_learning/analysis/`; every number below comes from one of them and can be
re-run. **Bottom line up front: your models are genuinely good and largely
reproduce under stricter validation.** The value I add is not a higher AUC — it is
(a) making the offline numbers *honest*, (b) removing a silent production
degradation at zero accuracy cost, and (c) a per-algorithm interpretation that
changes how the dashboard should talk about each prediction.

---

## 1. Methodology diff at a glance

| Dimension | Your pipeline (`train.py`) | My pipeline (`analysis/`) | Why it matters |
|---|---|---|---|
| Validation split | single random 80/20 (`random_state=42`) | repeated **StratifiedGroupKFold by `NameID`** (5×3) | 30.7% of rows are repeat songs (one has 22 snapshots). A random split puts the same song in train **and** test → optimistic. |
| Metric reporting | single-point AUC | mean **+ 95% band** over 15 folds | N=508 → estimates are noisy; a point AUC hides a ±0.06 band. |
| Primary metric | ROC-AUC | **AP (PR-AUC)** primary + Brier/ECE | classes are 20–47% positive; AP and calibration error are more honest than AUC alone. |
| Class imbalance | **SMOTE** for DW & RR | tested none / `scale_pos_weight` / SMOTE | SMOTE distorts calibration on small data — measured, not assumed. |
| Calibration | Platt fit **on the test split** | Platt fit on **out-of-fold** predictions | fitting calibration on the eval set is optimistic; OOF is leakage-free. |
| Feature contract | 13 features incl. 2 with **no live source** | **11 features** — drop the two that are imputed-to-0 at serving | removes train/serve skew at its root (see §3). |
| Volume target | raw 28-day streams | **log1p target** | raw target gives negative R² under honest CV; log tames the heavy tail. |

---

## 2. Where we AGREE — your work holds up

- **The classifiers are genuinely discriminative.** Under honest group-CV the ROC-AUC
  only drops ~0.02 vs your random split, *despite* heavy song duplication:

  | algo | your random-split AUC | honest group-CV ROC-AUC | inflation |
  |---|---|---|---|
  | DW | 0.937 | 0.919 [0.849–0.978] | +0.019 |
  | RR | 0.952 | 0.933 [0.901–0.978] | +0.019 |
  | Radio | 0.931 | 0.923 [0.881–0.966] | +0.007 |

  The leakage I worried about is real but **modest** — your headline AUCs are
  trustworthy to ~±0.02. Report them as "≈0.92" with a band, not "0.937".

- **XGBoost is the right family.** A scaled LogisticRegression and HistGradientBoosting
  were within noise on ROC-AUC but lost on AP (DW LogReg AP 0.675 vs XGB 0.711; RR
  LogReg 0.718 vs XGB 0.795). Keeping XGBoost is the correct call.

- **RR volume genuinely isn't predictable** — you suppressed it; I confirm it, and add
  that **DW volume is just as bad** (see §4).

- The **scaler-free decision** in `train.py` was correct and I kept it (XGBoost is
  monotone-invariant; the v1 scaler was pure train/serve skew).

---

## 3. Where we DIFFER #1 — the train/serve skew is the real bug (highest value)

Your model trains on 13 features, but `ml_inference.py` **imputes two of them to 0**
at serving because no live source exists:
`NonAlgoStreams28Days_log` and `HowManySongsDoYouHaveInRadioRightNow`.

In training those two are **non-zero in 97.6% of rows** (medians 2,362 and 10).
`NonAlgoStreams28Days_log` is even the **#1 feature by mutual information for DW**.
So the deployed model is fed 0 for features it learned were almost always large — it
runs off-distribution, and the lovely 0.92 offline AUC is **not** the number users get.

**The fix is counter-intuitive and cheap:** don't train on features you can't serve.
Dropping both costs essentially nothing under honest CV —

| algo | full 13-feat (offline mirage) | prod 11-feat (honest, no skew) | ΔROC-AUC |
|---|---|---|---|
| DW | 0.917 / 0.746 | 0.914 / 0.711 | −0.004 |
| RR | 0.936 / 0.800 | 0.936 / 0.795 | 0.000 |
| Radio | 0.925 / 0.915 | 0.927 / 0.912 | +0.002 |

(cells: ROC-AUC / AP). The information was redundant — `StreamsLast7Days_log` and the
engagement features already carry it. **`models/v3/` is trained on these 11 features,
so its offline metric *is* its production metric.** This is the single biggest
correctness win and it closes the long-standing "Phase-2 imputed features" caveat for
the *classifiers* (the live-data work is still worth doing, but it is no longer a
correctness blocker — it would be an accuracy *bonus*, now quantified at ≤0.004).

---

## 4. Where we DIFFER #2 — SMOTE, calibration, and the volume regressors

- **SMOTE is mildly harmful here.** On group-CV, SMOTE never beat "none" and hurt RR
  badly (AP 0.800 → 0.740, Brier 0.088 → 0.103). XGBoost handles 20% imbalance natively.
  v3 uses **no resampling**.

- **Calibration should be cross-fitted.** Your Platt fit on the 102-row test split is
  optimistic; v3 fits Platt on **out-of-fold** predictions over all 508 rows (same
  2-parameter `calibration.json` format, so `ml_inference` is unchanged). Cross-fitted
  isotonic was marginally better for DW (ECE 0.082 → 0.067) but within the CI — Platt
  keeps the infra simple, so I kept Platt.

- **All volume regressors are weak — DW worse than you think.** Under honest group-CV
  with the production features:

  | algo | raw-target R² | log-target R² | verdict |
  |---|---|---|---|
  | DW | −0.942 | −0.076 | **suppress** — not predictable |
  | RR | −0.181 | 0.226 | rough floor only, heavy caveat |
  | Radio | 0.208 | 0.334 | rough floor only |

  Your v2 reported DW R²=0.366 / Radio 0.564 — those are leakage-inflated. The honest
  numbers say **no volume forecast clears 0.5**. v3 regressors use the log target
  (never negative, tames the tail), but the recommendation is to surface volume only as
  a heavily-caveated floor and to **drop the DW volume number entirely**.

---

## 5. Where we DIFFER #3 — per-algorithm interpretation (new dashboard value)

I stripped the 3 stream-mechanical features (streams/ratio/velocity, which partly
*contain* the algo output) to ask: is each model *forecasting* or *scoring the present*?

| algo | prod (11) | leading (8, no streams) | metadata-only (6) | reading |
|---|---|---|---|---|
| DW | 0.914 | 0.906 | 0.791 | **forecast from levers** — skill lives in saves + playlist-adds |
| RR | 0.936 | 0.931 | **0.923** | **pure forecast** — predictable from release timing alone |
| Radio | 0.927 | 0.840 | 0.767 | **concurrency diagnostic** — mostly reads current streams |

This is the most useful *interpretive* difference and it should change the UI copy:

- **Release Radar → predict it on release day.** RR holds 0.923 AUC from artist +
  release metadata *only* (followers, `DaysSinceRelease`, `ReleasePhaseEarly`). You can
  give an artist their RR odds before a single stream lands. Frame it as a planning tool.
- **Discover Weekly → an actionable lever model.** DW barely needs streams; its signal
  is **saves and playlist-adds**. The existing marketing-lever framing is *correct* and
  earns its place — pushing saves genuinely moves DW odds.
- **Radio → a "you're trending" gauge, not a forecast.** Radio's skill collapses without
  concurrent streams. Don't sell it as prediction; sell it as a current-momentum readout.

---

## 6. Ranked recommendations & what shipped

> **Decision (2026-06-05):** ship every improvement BUT keep the 13-feature contract
> (rec #1 deferred to Phase 2). v3 was therefore retrained on all 13 features with the
> other methodology wins. Consequence: the train/serve skew (§3) is *not* removed yet,
> so Phase-2 live data **remains a real priority** (rec #7 below is updated accordingly).

| # | Change | Status |
|---|---|---|
| 1 | Drop the 2 never-served features (11-feat contract) | **deferred** to Phase 2 (user) — kept 13 |
| 2 | Drop SMOTE, cross-fit (OOF) calibration | **shipped** in v3 |
| 3 | Report AUC with CI bands in the scorecard | **shipped** (`ml_widgets`) |
| 4 | Suppress DW volume; caveat RR/Radio as floors | **shipped** (DW+RR suppressed, Radio floor) |
| 5 | Populate RR + Radio calibration bands | **shipped** (`ALGO_CALIBRATION_BANDS`) |
| 6 | Re-copy the UI per §5 (RR=forecast, DW=levers, Radio=momentum) | **shipped** (scorecard interpretations) |
| 7 | Phase-2 live data (NonAlgoStreams + RadioCount split) | **partly closed** (migration 052): both now have a manual S4A source and are served live once entered (`*_known` flags) → skew gone for filled tenants; the imputation caveat now fires only when no entry exists. Full auto-capture per S4A source still a Phase-2 item |

---

## 7. What is already built vs what shipping needs

**Built (this session):**
- `analysis/01_audit.py` → `audit.md` (grouping, leakage, skew, data quality)
- `analysis/02_validate.py` → `validation.md` (group-CV, imbalance, calibration bake-offs)
- `analysis/03_train.py` → `modeling.md` + **`models/v3/`** (11-feat classifiers, log
  regressors, OOF-Platt calibration, all artifacts in the v2 layout)
- `analysis/04_forecast_variant.py` → `forecast.md` (the §5 interpretation)

**Shipping (Phase F, pending your go-ahead on this report):**
- `src/utils/ml_inference.py`: `MODEL_VERSION="v3"`, `FEATURE_COLUMNS` → 11, drop the two
  imputed features from `build_features()` and from `_IMPUTED_FEATURES`, regressors read
  as `expm1(...)`.
- `src/dashboard/utils/algo_knowledge.py`: refresh `ALGO_MODEL_METRICS` (CV + CI),
  `ALGO_REGRESSOR_METRICS` (honest R², DW suppressed), add `ALGO_CALIBRATION_BANDS["RR"]`
  and `["RADIO"]`, and the §5 framing strings.
- `src/dashboard/utils/ml_widgets.py`: show the CI band in the scorecard.
- `tests/test_ml_inference.py`: re-baseline against v3 (deliberate, noted in DEVLOG).
- Promote `analysis/03_train.py` (or fold into `train.py`) as the canonical trainer.

**Risk note:** changing `FEATURE_COLUMNS` is a contract change; v2 `.ubj` files stay on
disk and `model_version` is in the predictions UNIQUE key, so the rollover is clean and
reversible (old predictions preserved, new ones tagged `v3`).
