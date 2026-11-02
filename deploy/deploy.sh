#!/usr/bin/env bash
# Deploys the currently-checked-out branch of this repo to the Aira HRMS
# production service on this VPS. Invoked over SSH by the GitHub Actions
# workflow (.github/workflows/deploy.yml) via a forced-command deploy key,
# but safe to run by hand for a manual redeploy too.
set -euo pipefail

REPO_DIR="/srv/apps/aira/repo"
BACKEND_DIR="$REPO_DIR/backend"
FRONTEND_DIR="$REPO_DIR/frontend"
VENV="/srv/apps/aira/venv"
BRANCH="New-AI"
HEALTH_URL="https://aira.nxsys.in/login"
DEPLOYED_COMMIT_FILE="$REPO_DIR/.git/last_successful_deploy"

cd "$REPO_DIR"

OLD_HEAD=$(git rev-parse HEAD)

echo "==> Fetching origin/$BRANCH"
git fetch origin "$BRANCH"

echo "==> Fast-forwarding to origin/$BRANCH"
if ! git merge --ff-only "origin/$BRANCH"; then
    echo "FAIL: server checkout has diverged from origin/$BRANCH (local commits or uncommitted changes present)." >&2
    echo "Refusing to overwrite - resolve manually on the server, then re-run the deploy." >&2
    exit 1
fi

NEW_HEAD=$(git rev-parse HEAD)

# The current process may have loaded an older copy of this script before the
# fast-forward. Re-exec the checked-out version so its deploy logic applies.
if [ "$OLD_HEAD" != "$NEW_HEAD" ] && git diff --name-only "$OLD_HEAD" "$NEW_HEAD" | grep -q '^deploy/deploy.sh$'; then
    echo "==> Deploy script changed; restarting with the fetched version"
    exec bash "$REPO_DIR/deploy/deploy.sh"
fi

LAST_DEPLOYED=""
if [ -f "$DEPLOYED_COMMIT_FILE" ]; then
    LAST_DEPLOYED=$(tr -d '[:space:]' < "$DEPLOYED_COMMIT_FILE")
fi

if [ "$LAST_DEPLOYED" = "$NEW_HEAD" ]; then
    echo "==> Already successfully deployed at $NEW_HEAD, nothing to do."
    exit 0
fi

FULL_DEPLOY=0
if [ -z "$LAST_DEPLOYED" ] \
    || ! git cat-file -e "$LAST_DEPLOYED^{commit}" 2>/dev/null \
    || ! git merge-base --is-ancestor "$LAST_DEPLOYED" "$NEW_HEAD"; then
    echo "==> No valid successful-deploy record; performing a full deploy."
    FULL_DEPLOY=1
    CHANGED_FILES=""
else
    echo "==> Deploying $LAST_DEPLOYED -> $NEW_HEAD"
    CHANGED_FILES=$(git diff --name-only "$LAST_DEPLOYED" "$NEW_HEAD")
fi
echo "$CHANGED_FILES"

changed() {
    [ "$FULL_DEPLOY" = "1" ] || printf '%s\n' "$CHANGED_FILES" | grep -qE "$1"
}

if changed "^backend/requirements.txt$"; then
    echo "==> requirements.txt changed - installing backend dependencies"
    "$VENV/bin/pip" install -r "$BACKEND_DIR/requirements.txt"
fi

cd "$BACKEND_DIR"

echo "==> Running database migrations"
"$VENV/bin/python" manage.py migrate --noinput

if changed "^frontend/(app/|components/|hooks/|lib/|types/|public/|package.*\.json|next\.config\.ts)"; then
    echo "==> Frontend changed - installing deps and rebuilding"
    cd "$FRONTEND_DIR"
    npm ci
    npm run build
    cd "$BACKEND_DIR"
fi

echo "==> Collecting static files"
"$VENV/bin/python" manage.py collectstatic --noinput

echo "==> Restarting services"
sudo /usr/bin/systemctl restart aira-web.service
sudo /usr/bin/systemctl restart aira-celery.service
sudo /usr/bin/systemctl restart aira-celery-beat.service
sudo /usr/bin/systemctl restart aira-frontend.service

echo "==> Waiting for services to come up"
sleep 3

echo "==> Health check: $HEALTH_URL"
HTTP_CODE=$(curl -s -o /dev/null -w "%{http_code}" --max-time 15 "$HEALTH_URL")
if [ "$HTTP_CODE" != "200" ]; then
    echo "FAIL: health check returned HTTP $HTTP_CODE (expected 200)." >&2
    exit 1
fi

printf '%s\n' "$NEW_HEAD" > "$DEPLOYED_COMMIT_FILE.tmp"
mv "$DEPLOYED_COMMIT_FILE.tmp" "$DEPLOYED_COMMIT_FILE"
echo "==> Deploy succeeded: ${LAST_DEPLOYED:-<full deploy>} -> $NEW_HEAD"
