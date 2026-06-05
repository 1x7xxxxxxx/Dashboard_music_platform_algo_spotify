# Forward-looking reframe — is the skill real prediction or concurrency?

group-CV ROC-AUC / AP by feature set. `prod` includes the 3 stream-mechanical features; `leading` drops them; `metadata` keeps only pre-trigger artist/release signals.

| algo | prod (11) | leading (8) | metadata (6) |
|---|---|---|---|
| dw | 0.914 / 0.711 | 0.906 / 0.702 | 0.791 / 0.520 |
| rr | 0.936 / 0.795 | 0.931 / 0.773 | 0.923 / 0.744 |
| radio | 0.927 / 0.912 | 0.840 / 0.803 | 0.767 / 0.733 |

*If `leading`/`metadata` stay close to `prod`, the model is genuinely forecasting from plannable signals. A large drop means the skill was mostly reading streams that already contain the algo output.*
