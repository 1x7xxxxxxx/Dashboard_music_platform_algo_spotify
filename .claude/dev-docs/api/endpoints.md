# API Endpoints — Dashboard_music_platform_algo_spotify

> Auto-populated by `generate-dev-docs.py --framework {{FRAMEWORK}}`.

## Route Inventory

<!-- AUTO:ROUTES_BEGIN -->
*Auto-generated 2026-08-21 — 8 routes*

| Method | Path | Function | Description |
|--------|------|----------|-------------|
| `GET` | `/health` | `health` | Returns ``{"status": "ok"}`` — no auth required. |
| `GET` | `/me` | `get_me` | get_me |
| `GET` | `/predictions` | `get_predictions` | get_predictions |
| `POST` | `/stripe` | `stripe_webhook` | Verify Stripe signature and process billing events. |
| `GET` | `/summary` | `get_summary` | get_summary |
| `GET` | `/timeline` | `get_timeline` | get_timeline |
| `POST` | `/token` | `login` | OAuth2 password flow against saas_users (username OR email + bcrypt). |
| `GET` | `/videos` | `get_videos` | get_videos |

### Grouped by resource

#### /health
- `GET /health`  — health

#### /me
- `GET /me`  — get_me

#### /predictions
- `GET /predictions`  — get_predictions

#### /stripe
- `POST /stripe`  — stripe_webhook

#### /summary
- `GET /summary`  — get_summary

#### /timeline
- `GET /timeline`  — get_timeline

#### /token
- `POST /token`  — login

#### /videos
- `GET /videos`  — get_videos
<!-- AUTO:ROUTES_END -->

## Endpoint Details

<!-- AUTO:DETAILS_BEGIN -->
TODO: run generate-dev-docs.py to populate
<!-- AUTO:DETAILS_END -->

## Error envelope (standard)

```json
{
  "detail": "Human-readable message",
  "code": "MACHINE_READABLE_CODE",
  "status": 4xx
}
```

## Auth conventions

- TODO: describe auth scheme (Bearer, API key, session, etc.)
