Read and analyze the recent Airflow logs to help diagnose pipeline issues.

## Steps

Run the following commands using the Bash tool and analyze the output:

```bash
# Scheduler logs (most important — where DAG errors appear)
docker.exe logs --tail 80 airflow_scheduler 2>&1

# Webserver logs (if UI issues)
docker.exe logs --tail 30 airflow_webserver 2>&1

# PostgreSQL logs (if DB connection issues)
docker.exe logs --tail 20 postgres_spotify_airflow 2>&1
```

If `docker.exe` is not found at the default path, try:
```bash
/mnt/c/Program\ Files/Docker/Docker/resources/bin/docker.exe logs --tail 80 airflow_scheduler 2>&1
```

## Analysis

After reading the logs:
1. Identify any ERROR or CRITICAL lines and their root cause.
2. Check for import errors (common when a new `src/` file has a syntax issue).
3. Check for DB connection failures (means `docker-compose up -d` may be needed).
4. Check for DAG parse errors (often caused by module-level imports — must be inside task functions).
5. Suggest a targeted fix, not just "restart everything".

## If no containers found

Remind the user to start the stack: `docker-compose up -d`
