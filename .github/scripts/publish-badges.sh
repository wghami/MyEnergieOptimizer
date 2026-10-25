#!/usr/bin/env bash
# Publish shields.io endpoint documents (*.json in $1) to the badges branch (CI-10).
# The branch holds only badge data, so badge updates never touch main or its history.
set -euo pipefail
src=$(realpath "$1")
branch=${BADGES_BRANCH:-badges}
url="https://x-access-token:${GH_TOKEN}@github.com/${GITHUB_REPOSITORY}.git"
work=$(mktemp -d)
git -C "${work}" init -q
git -C "${work}" config user.name "github-actions[bot]"
git -C "${work}" config user.email "41898282+github-actions[bot]@users.noreply.github.com"
for attempt in 1 2 3; do
  if git -C "${work}" fetch -q --depth 1 "${url}" "${branch}" 2>/dev/null; then
    git -C "${work}" checkout -q -f -B "${branch}" FETCH_HEAD
  else
    git -C "${work}" checkout -q --orphan "${branch}"
  fi
  cp "${src}"/*.json "${work}/"
  git -C "${work}" add -A
  if git -C "${work}" diff --cached --quiet; then
    echo "badges unchanged"
    exit 0
  fi
  git -C "${work}" commit -q -m "chore: update badges"
  if git -C "${work}" push -q "${url}" "HEAD:${branch}"; then
    exit 0
  fi
  echo "push raced with another badge update, retrying (${attempt}/3)"
done
exit 1
