# KTS — Operations runbook (Phase 1)

## Environments

| | Staging | Production |
|:--|:--|:--|
| Region | Mumbai (`ap-south-1` / `asia-south1`) | Mumbai |
| API | 1 container, 2 gunicorn workers | 2+ containers behind a load balancer |
| Postgres | Managed Postgres 16, smallest tier | Managed Postgres 16, PITR enabled |
| Redis | Optional (rate-limit storage) | Required once more than one container runs |
| Auth | Firebase project `kts-staging` | Firebase project `kts-prod` |

Keep data in India: choose the Mumbai region for the database, the container
host and the object storage bucket. Render does not currently provide a Mumbai
region; the included staging blueprint uses Singapore and therefore does not meet
a strict in-country residency requirement. Use an India-region provider when that
requirement applies.

## Release steps

1. CI is green on `main` (ruff + pytest against Postgres + Docker build).
2. Run migrations as a one-off job: `alembic upgrade head`.
3. Deploy the new image. The app never creates tables by itself.

The Render blueprint enforces this order with `autoDeployTrigger: checksPass` and
`preDeployCommand: alembic upgrade head`. Add the Firebase service-account JSON
as a secret file at `/etc/secrets/firebase-credentials.json`; never store it in
Git or as a plain environment variable.

Required production settings: `APP_ENV=production`, a random 32+ character
`JWT_SECRET_KEY`, `AUTH_DEV_STUB=false`, a Postgres `DATABASE_URL`, the Firebase
service-account file at `FIREBASE_CREDENTIALS_PATH`, `RATE_LIMIT_STORAGE_URI=redis://…`
and `SENTRY_DSN`. The app refuses to start in staging/production with an insecure
secret, the dev auth stub, or SQLite.

## Existing databases created with `create_all`

Earlier builds created tables at startup. Those databases hold only test data:
drop and recreate them, then run `alembic upgrade head`. Do not `alembic stamp`
an old schema; the columns have changed.

## Monitoring

- **Sentry**: set `SENTRY_DSN`. To verify, raise a test error from a Python shell in the
  container: `python -c "from app.logging_config import init_sentry; init_sentry(); 1/0"`.
- **Logs**: JSON lines on stdout (`ts, level, logger, msg, request_id, method, path,
  status, duration_ms`). Every response carries an `x-request-id` header.
- **Health**: `GET /health` (also used by the Docker `HEALTHCHECK`).

## Backups

Nightly logical backup, kept 30 days, in a private bucket in the same region:

```bash
pg_dump --format=custom --no-owner "$DATABASE_URL" > kts-$(date +%F).dump
aws s3 cp kts-$(date +%F).dump s3://kts-backups/nightly/ --sse AES256
```

Managed Postgres point-in-time recovery stays on as the first line of defence;
the dump protects against provider-level loss and lets you restore anywhere.

## Restore drill (do this once before the first real distributor, then quarterly)

1. Create an empty database `kts_restore_test`.
2. `aws s3 cp s3://kts-backups/nightly/<latest>.dump .`
3. `pg_restore --no-owner --dbname "$RESTORE_URL" <latest>.dump`
4. Point a staging container at it and check: `alembic current` shows head;
   `GET /health` is ok; signing in as a known owner shows the expected bills count.
5. Record the date, the dump size, how long the restore took and who ran it below.

| Date | Dump | Restore time | Result | By |
|:--|:--|:--|:--|:--|
| _not yet run_ | | | | |
