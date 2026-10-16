# Security policy

## Scope

- The production application: `https://app.streamlytics.fr` (Streamlit dashboard) and its REST API.
- This repository: application code, Airflow DAGs, migrations, CI workflows.

In scope in particular: tenant isolation (one artist reading or writing another artist's
data), authentication and JWT handling, storage of third-party credentials (Spotify,
Meta, YouTube, SoundCloud tokens), injection (SQL, template), secrets in the repository.

## Supported version

Only what runs in production — the `main` branch. There are no maintained releases.

## Reporting a vulnerability

Use GitHub private vulnerability reporting: **Security tab → "Report a vulnerability"**
on this repository. The report stays private between you and the maintainer.

Please do **not**:

- open a public issue or pull request describing the vulnerability;
- access, modify or delete data that is not yours — use your own account, and stop at
  the first proof that another tenant's data is reachable;
- run load or denial-of-service tests, or automated scanners against production.

## What to expect

This project has a single maintainer. Acknowledgement within **7 days**; a fix or a
mitigation plan follows, and you are told when it ships.

## Safe harbour

Good-faith research that follows this policy will not be pursued legally. If in doubt
about whether something is in scope, ask in the report before going further.
