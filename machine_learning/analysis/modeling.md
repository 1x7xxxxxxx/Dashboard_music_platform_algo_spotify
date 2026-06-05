# Independent modeling — feature contract, champion, regressors

Production feature contract drops ['NonAlgoStreams28Days_log', 'HowManySongsDoYouHaveInRadioRightNow'] (no live source). group-CV = StratifiedGroupKFold(5)×3 by NameID.

## A. Cost of dropping the two never-served features

| algo | full 13-feat ROC-AUC / AP | prod 11-feat ROC-AUC / AP | ΔROC-AUC |
|---|---|---|---|
| dw | 0.917 / 0.746 | 0.914 / 0.711 | **-0.004** |
| rr | 0.936 / 0.800 | 0.936 / 0.795 | **+0.000** |
| radio | 0.925 / 0.915 | 0.927 / 0.912 | **+0.002** |

*The 11-feature number is what production can actually deliver (no skew). The full-13 number is the offline mirage when the two imputed-to-0 features are present.*

## B. Champion estimator (production 11 features, group-CV)

| algo | XGBoost | HistGB | LogReg (scaled) |
|---|---|---|---|
| dw | 0.914 / 0.711 | 0.906 / 0.712 | 0.917 / 0.675 |
| rr | 0.936 / 0.795 | 0.931 / 0.774 | 0.906 / 0.718 |
| radio | 0.927 / 0.912 | 0.928 / 0.917 | 0.926 / 0.909 |

*Cells: ROC-AUC / AP. Picking XGBoost unless a simpler model matches it within the CI (then prefer the simpler, better-calibrated one).*

## C. Volume regressors — raw vs log target (group-CV R², prod feats)

| algo | raw-target R² | log-target R² |
|---|---|---|
| dw | -0.942 | -0.076 |
| rr | -0.181 | 0.226 |
| radio | 0.208 | 0.334 |

*R² < 0 means worse than predicting the mean. Use this to decide which volume forecasts are honest enough to surface.*

## D. Final artifacts

Trained v3 (**13-feature** shipped contract per user decision; §A/§B remain the 11-feat analysis), log-target regressors, no SMOTE, OOF-Platt calibration -> `/mnt/c/Users/timot/Desktop/Dashboard_music_platform_algo_spotify/machine_learning/models/v3`
