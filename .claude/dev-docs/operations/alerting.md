# Alerting — Dashboard_music_platform_algo_spotify

## Alert thresholds

| Alert | Condition | Severity | Action |
|-------|-----------|----------|--------|
| TODO | TODO | WARNING | TODO |

## Alert flow

```mermaid
flowchart TD
    A[Condition detected] --> B{Severity?}
    B -->|WARNING| C[Log + TODO]
    B -->|CRITICAL| D[Log + Notify + TODO]
```

## Cooldown / deduplication rules

- TODO: describe cooldown windows, dedup logic
