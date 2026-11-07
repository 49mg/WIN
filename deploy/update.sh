#!/usr/bin/env bash
# Update WIN on the server to the latest code on GitHub:  ./deploy/update.sh
# Only WIN's own containers are rebuilt; nginx and the other sites are not touched.
set -euo pipefail
cd "$(dirname "$0")/.."

echo "== pulling the latest code"
git pull --ff-only

echo "== rebuilding and restarting WIN"
docker compose -f docker-compose.prod.yml up -d --build

echo "== waiting for the API (it loads the embedding model at start, ~30-60 s)"
for _ in $(seq 60); do
  if curl -sf http://127.0.0.1:8100/health >/dev/null; then
    echo "API is up:  $(curl -s http://127.0.0.1:8100/health)"
    docker image prune -f >/dev/null  # drop the old images from this build
    exit 0
  fi
  sleep 3
done
echo "The API did not come up. Logs: docker compose -f docker-compose.prod.yml logs backend" >&2
exit 1
