#!/usr/bin/env bash
# Fails if any non-merge commit in BASE..HEAD lacks a Signed-off-by trailer
# matching its author email (Developer Certificate of Origin).
set -euo pipefail

base="$1"
head="$2"
status=0

for sha in $(git rev-list --no-merges "${base}..${head}"); do
  email="$(git log -1 --format='%ae' "$sha")"
  if ! git log -1 --format='%(trailers:key=Signed-off-by,valueonly)' "$sha" \
      | grep -qiF "<${email}>"; then
    echo "::error::Commit ${sha} has no Signed-off-by line for ${email}. Fix with: git rebase --signoff ${base}"
    status=1
  fi
done

if [ "$status" -eq 0 ]; then
  echo "All commits are signed off."
fi
exit "$status"
