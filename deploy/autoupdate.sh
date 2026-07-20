#!/usr/bin/env bash
# Проверяет новые коммиты в репозитории и, если они есть, подтягивает их
# и пересобирает контейнер. Рассчитан на запуск по таймеру (см.
# movirevo-autoupdate.timer), а не вручную.
set -euo pipefail

REPO_DIR="${REPO_DIR:-/opt/movirevo}"
BRANCH="${BRANCH:-main}"

cd "$REPO_DIR"

git fetch origin "$BRANCH"
LOCAL=$(git rev-parse HEAD)
REMOTE=$(git rev-parse "origin/$BRANCH")

if [ "$LOCAL" = "$REMOTE" ]; then
  exit 0
fi

echo "$(date -Is) Обнаружены новые коммиты (${LOCAL:0:7} -> ${REMOTE:0:7}), обновляю..."
git reset --hard "origin/$BRANCH"
docker compose up -d --build
echo "$(date -Is) Готово: сервер обновлён до ${REMOTE:0:7}"
