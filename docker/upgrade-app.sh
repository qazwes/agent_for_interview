#!/bin/sh
# 从 my-agent 目录执行：sh docker/upgrade-app.sh
set -eu
cd "$(dirname "$0")/.."
docker compose --env-file .env -f docker/docker-compose.yaml exec -T mysql sh /docker-entrypoint-initdb.d/zz-agent-app.sh
