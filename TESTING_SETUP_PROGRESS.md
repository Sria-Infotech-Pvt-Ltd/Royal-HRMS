# Testing Setup Progress

Branch: `chore/testing-foundation` (created from `New-AI`; never pushed to New-AI/demo/main).

## Pre-existing uncommitted work (NOT touched by this task)

52 entries were already modified/deleted/untracked when this task started (accounts serializers/views, hrms models/serializers/settlement, `config/settings.py`,
deleted `docs/*` and `ONBOARDING.md`, frontend employee/ess/hire/payslip/separation files, new `hrms/migrations/0047_*`, etc.).
This task stages only files it created or changed itself. Snapshot of the list was taken at start.

## Step 1 - Discovery (partial: blocked before running tests)

### How tests are run today
- `cd backend && python manage.py test` (Django runner, ~2,013 `test_*` methods). CI (`.github/workflows/backend-tests.yml`) runs it on a `postgres:16` service,
  plus `manage.py check`, `makemigrations --check`, `scripts/check_no_new_choices.py`, `scripts/check_no_permission_migrations.py`.
- Frontend: `npm test` (`vitest run`), `npm run lint` (eslint). 16 frontend test files. No Playwright, no coverage tooling.
- Deploy: `.github/workflows/deploy.yml` on push to `New-AI` (SSH -> `deploy/deploy.sh`). Not to be modified.

### Test count per backend app (test methods)
accounts 406, announcements 11, assessments 16, attendance 159, branch 25, dashboard 5, hrms 100, notifications 0, payroll 239, performance 51,
platform_core 275, recruitment 38, voice_commands 688. Total 2,013.

### Findings / risks
1. **`backend/.env` `DATABASE_URL` points to a Neon cloud host.** `config/settings.py` requires `DATABASE_URL`, and Django's runner creates `test_*` on the same server.
   Running tests with the current `.env` would write to the shared cloud server, which violates safety rule 2. No tests were run.
2. **There is no `USE_SQLITE=1` switch in the code.** `settings.py` raises `ImproperlyConfigured` unless the URL is PostgreSQL (TEAM_CONTEXT.md line 4321: "SQLite support was removed").
   The "run once on SQLite" part of Step 1 and the SQLite-vs-Postgres comparison in Step 2 are therefore not possible as written.
3. **Docker is not installed** on this machine. A local PostgreSQL **17** Windows service (`postgresql-x64-17`) and Redis are running. Credentials for it are unknown to me.
4. `.env` is gitignored (good). `backend/celerybeat-schedule*` files exist in the working dir (gitignored per TEAM_CONTEXT).
5. Existing CI uses Python 3.13, Postgres 16, `DB_SSL_MODE=disable`; settings already honour `DB_SSL_MODE` and `TEST_DB_SUFFIX`, which helps Step 2.
6. `voice_commands` holds 34% of all tests and 44 test files.

### Open issue
Need a local Postgres to run anything. See decision below.

## Resume point
Step 1 report written. Next: obtain a local Postgres connection (decision pending), then Step 2.
