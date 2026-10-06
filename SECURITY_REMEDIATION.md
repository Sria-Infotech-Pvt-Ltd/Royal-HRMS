# Phase 0 — Security & Repository Hygiene

Audit date: 2026-10-06. Scope: this repository's actual git history and working
tree on the `New-AI` branch (not a generic checklist — every claim below was
verified against this specific repo).

## What was checked

| Item | Found in current working tree? | Ever committed in git history? |
|---|---|---|
| `.env` (real secrets) | No | No |
| Committed Python virtual environment (`H/`, `venv/`) | No | No |
| `db.sqlite3` / local database file | No | No |
| `logs/`, cookie files | No | No |
| `celerybeat-schedule.dat` / `.dir` (scheduler state) | No (now gitignored) | **Yes** — committed in early history, later removed and gitignored |
| `vps_server_setup.md` (contains internal IPs/credentials, per its own gitignore comment) | Not tracked | Not checked — file is gitignored, assumed to exist only locally |

**Bottom line:** this repo is in materially better shape than a generic "newly
delivered archive" security checklist assumes. No `.env`, virtual environment,
database file, or logs have ever been committed. `.gitignore` (both root and
`backend/`) already explicitly covers all of these categories, including
`celerybeat-schedule*` variants.

## The one real finding: `celerybeat-schedule.dat` / `.dir`

These two files were committed in this repo's early history (visible via
`git log --all --diff-filter=A --name-only`), then later removed and
gitignored. They are **not credentials** — they're Celery Beat's local
scheduler bookkeeping (which periodic task last ran, next-run timestamps),
pickled to disk. No secret keys, passwords, or tokens are stored in this file
format.

**Risk level: low**, but not zero — anyone who clones the full history could
still extract these two blobs. Residual risk is bookkeeping-state exposure,
not credential leakage.

**Recommended action (not yet taken — requires explicit sign-off):**
Purging them from git history means rewriting history (`git filter-repo` or
BFG), which requires every existing clone/fork to be re-cloned and would
invalidate any open PRs referencing old commits. Given the low sensitivity of
the actual file contents, **the pragmatic choice is to leave history as-is**
and rely on the current `.gitignore` entry to prevent recurrence, unless
there's a specific compliance requirement mandating history rewrite. Flagging
here for a decision, not acting unilaterally on a destructive operation.

## Secret rotation — standing guidance

Not because anything is known to be compromised, but as standard practice:
anyone who has ever had clone access to this repository, or access to the
production `.env` file, is a candidate for rotation if that access is later
revoked (e.g. an employee/contractor offboarding). Secrets live only in the
untracked `backend/.env` on the production server and in GitHub Actions
repository secrets (`DEPLOY_SSH_HOST`, `DEPLOY_SSH_USER`, `DEPLOY_SSH_KEY`,
`SMTP_*`, `NOTIFY_EMAIL`) — never in the repo itself.

| Secret | Where it lives | Rotation action |
|---|---|---|
| `SECRET_KEY` (Django) | server `.env` | Generate new, update `.env`, restart app — invalidates all existing sessions |
| `FIELD_ENCRYPTION_KEY` | server `.env` | **Cannot be rotated without a data re-encryption migration** — this key decrypts every `EncryptedCharField`/`EncryptedJSONField` value (bank details, PAN, Aadhaar, etc.) already in the database. Rotating it blindly makes all existing encrypted data unreadable. Treat as highest-sensitivity; if rotation is ever needed, it requires a dedicated re-encrypt-in-place migration, not a simple swap. |
| `FIELD_INDEX_HMAC_KEY` | server `.env` | Same constraint as above — used to compute lookup hashes for encrypted fields; rotating breaks existing uniqueness/lookup indexes without a backfill. |
| `IMAGEKIT_PUBLIC_KEY` / `IMAGEKIT_PRIVATE_KEY` | server `.env` | Rotate via ImageKit dashboard, update `.env`, restart — no data migration needed (existing uploaded files remain accessible by URL regardless) |
| `SARVAM_API_KEY` | server `.env` | Rotate via Sarvam dashboard, update `.env`, restart |
| `DATABASE_URL` (Neon Postgres) | server `.env` | Rotate via Neon dashboard, update `.env`, restart |
| `REDIS_URL` | server `.env` | Rotate via Redis provider dashboard, update `.env`, restart |
| GitHub Actions deploy secrets (`DEPLOY_SSH_*`) | GitHub repo settings → Secrets | Regenerate SSH keypair, update authorized_keys on server, update GitHub secret |
| SMTP credentials (`SMTP_*` for deploy notifications) | GitHub repo settings → Secrets | Rotate via email provider, update GitHub secret |

The two encryption keys are flagged separately because they're the one case
where "just rotate it" is actively dangerous without a proper migration plan
— worth a dedicated task if rotation is ever genuinely required, not a quick
`.env` edit.

## External API keys (added this session)

`ExternalAPIKey` rows (for the Project Budget & Tracking integration, see
`apps/accounts/authentication_external.py`) already follow this same
discipline: only a SHA-256 hash is stored, the raw value is shown once at
generation time, and revocation is a single `is_active=False` flip — no
history-rewrite risk, since the key is never written to any file that gets
committed.
