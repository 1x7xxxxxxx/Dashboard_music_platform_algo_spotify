# v3 scorecard metrics (group-CV OOF)

```python
{
  "DW": {
    "model_version": "v3",
    "test_n": 508,
    "eval": "group-CV (OOF)",
    "auc": 0.917,
    "auc_ci": [
      0.846,
      0.977
    ],
    "pr_ap": 0.746,
    "ap_ci": [
      0.589,
      0.89
    ],
    "confusion": {
      "TN": 379,
      "FP": 25,
      "FN": 38,
      "TP": 66
    },
    "precision": 0.725,
    "recall": 0.635,
    "f1": 0.677,
    "accuracy": 0.876,
    "lift_top10": 3.8,
    "baseline_accuracy": 0.795
  },
  "RR": {
    "model_version": "v3",
    "test_n": 508,
    "eval": "group-CV (OOF)",
    "auc": 0.936,
    "auc_ci": [
      0.901,
      0.979
    ],
    "pr_ap": 0.8,
    "ap_ci": [
      0.66,
      0.922
    ],
    "confusion": {
      "TN": 388,
      "FP": 20,
      "FN": 39,
      "TP": 61
    },
    "precision": 0.753,
    "recall": 0.61,
    "f1": 0.674,
    "accuracy": 0.884,
    "lift_top10": 4.6,
    "baseline_accuracy": 0.803
  },
  "RADIO": {
    "model_version": "v3",
    "test_n": 508,
    "eval": "group-CV (OOF)",
    "auc": 0.925,
    "auc_ci": [
      0.882,
      0.967
    ],
    "pr_ap": 0.915,
    "ap_ci": [
      0.851,
      0.966
    ],
    "confusion": {
      "TN": 227,
      "FP": 42,
      "FN": 49,
      "TP": 190
    },
    "precision": 0.819,
    "recall": 0.795,
    "f1": 0.807,
    "accuracy": 0.821,
    "lift_top10": 2.0,
    "baseline_accuracy": 0.53
  }
}
```
