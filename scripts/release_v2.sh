#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

TAG_NAME="${1:-v2.0.0}"
RELEASE_NOTES_FILE="docs/RELEASE-v2.0.0.md"

if [[ -n "$(git status --porcelain)" ]]; then
  echo "[RELEASE] ERROR: working tree is not clean."
  git status --short
  exit 1
fi

CURRENT_BRANCH="$(git branch --show-current)"
if [[ "$CURRENT_BRANCH" != "main" ]]; then
  echo "[RELEASE] ERROR: release must run from 'main' (current: $CURRENT_BRANCH)."
  exit 1
fi

if ! git rev-parse "$TAG_NAME" >/dev/null 2>&1; then
  echo "[RELEASE] ERROR: tag '$TAG_NAME' does not exist locally."
  exit 1
fi

TAG_COMMIT="$(git rev-list -n 1 "$TAG_NAME")"
HEAD_COMMIT="$(git rev-parse HEAD)"
if [[ "$TAG_COMMIT" != "$HEAD_COMMIT" ]]; then
  echo "[RELEASE] ERROR: tag '$TAG_NAME' is not at HEAD."
  echo "[RELEASE]        tag:  $TAG_COMMIT"
  echo "[RELEASE]        head: $HEAD_COMMIT"
  echo "[RELEASE] Move the tag to HEAD before publishing, for example:"
  echo "  git tag -fa $TAG_NAME -m \"$TAG_NAME\""
  exit 1
fi

if [[ ! -f "$RELEASE_NOTES_FILE" ]]; then
  echo "[RELEASE] ERROR: release notes file not found: $RELEASE_NOTES_FILE"
  exit 1
fi

echo "[RELEASE] Pushing branch and tag..."
git push origin main
git push origin "$TAG_NAME"

if command -v gh >/dev/null 2>&1; then
  echo "[RELEASE] Creating GitHub release via gh CLI..."
  if ! gh release create "$TAG_NAME" --title "$TAG_NAME" --notes-file "$RELEASE_NOTES_FILE"; then
    echo "[RELEASE] ERROR: failed to create GitHub release with gh."
    exit 1
  fi
  echo "[RELEASE] GitHub release created: $TAG_NAME"
else
  echo "[RELEASE] gh CLI not found. Run these commands manually:"
  echo "  git push origin main"
  echo "  git push origin $TAG_NAME"
  echo "  gh release create $TAG_NAME --title \"$TAG_NAME\" --notes-file $RELEASE_NOTES_FILE"
fi
