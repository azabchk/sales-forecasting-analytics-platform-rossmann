#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

TAG_NAME="${TAG_NAME:-v2.0.0}"
NOTES_FILE="${NOTES_FILE:-docs/RELEASE-v2.0.0.md}"
APPLY="${APPLY:-0}"

print_plan() {
  echo "[PLAN] Release + Deploy Order"
  echo "1) git checkout main"
  echo "2) git pull --ff-only origin main"
  echo "3) git tag -l ${TAG_NAME}"
  echo "4) git push origin main"
  echo "5) git push origin ${TAG_NAME}"
  echo "6) gh release create ${TAG_NAME} --title \"${TAG_NAME}\" --notes-file ${NOTES_FILE}"
  echo "7) Deploy backend (Render/Fly) using docs/DEPLOY-BACKEND-PAAS.md"
  echo "8) Deploy frontend (Vercel) using docs/DEPLOY-VERCEL.md"
  echo "9) Configure DNS/SSL using docs/DOMAIN-DNS.md"
  echo "10) Run production check: BACKEND_PUBLIC_URL=https://api.yourcompany.com bash scripts/prod_env_check.sh"
}

print_plan

if [[ "$APPLY" != "1" ]]; then
  echo "[PLAN] Dry run only. Set APPLY=1 to execute release commands."
  exit 0
fi

if [[ -n "$(git status --porcelain)" ]]; then
  echo "[PLAN] ERROR: working tree is not clean"
  git status --short
  exit 1
fi

if [[ "$(git branch --show-current)" != "main" ]]; then
  echo "[PLAN] ERROR: branch must be main"
  exit 1
fi

if ! git rev-parse "$TAG_NAME" >/dev/null 2>&1; then
  echo "[PLAN] ERROR: tag not found locally: $TAG_NAME"
  exit 1
fi

if [[ ! -f "$NOTES_FILE" ]]; then
  echo "[PLAN] ERROR: notes file missing: $NOTES_FILE"
  exit 1
fi

echo "[PLAN] Pushing branch and tag..."
git push origin main
git push origin "$TAG_NAME"

if command -v gh >/dev/null 2>&1; then
  if gh release view "$TAG_NAME" >/dev/null 2>&1; then
    echo "[PLAN] Release already exists for $TAG_NAME (skipping create)."
  else
    gh release create "$TAG_NAME" --title "$TAG_NAME" --notes-file "$NOTES_FILE"
    echo "[PLAN] Release created: $TAG_NAME"
  fi
else
  echo "[PLAN] gh CLI not installed/authenticated. Run manually:"
  echo "gh release create $TAG_NAME --title \"$TAG_NAME\" --notes-file $NOTES_FILE"
fi
