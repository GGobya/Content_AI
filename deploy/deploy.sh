#!/usr/bin/env bash
# Деплой бота на сервере. Запускается GitHub Actions self-hosted runner'ом
# (см. .github/workflows/deploy.yml), либо вручную: ./deploy/deploy.sh [branch]
#
# Предполагает, что репозиторий уже склонирован в $APP_DIR и там лежит
# заполненный .env (создаётся один раз вручную, в git не попадает).
set -euo pipefail

APP_DIR="${APP_DIR:-/opt/content_ai}"
BRANCH="${1:-main}"
SERVICE_NAME="${SERVICE_NAME:-content-ai-bot}"

cd "$APP_DIR"

echo "==> git fetch/reset на origin/${BRANCH}"
git fetch origin "$BRANCH"
git reset --hard "origin/${BRANCH}"

if [ ! -d .venv ]; then
  echo "==> Создаю venv"
  python3 -m venv .venv
fi

echo "==> Устанавливаю зависимости"
"$APP_DIR/.venv/bin/pip" install -q --upgrade pip
"$APP_DIR/.venv/bin/pip" install -q -r requirements.txt

echo "==> Перезапускаю сервис ${SERVICE_NAME}"
sudo systemctl restart "$SERVICE_NAME"
sleep 2
sudo systemctl status "$SERVICE_NAME" --no-pager -l | head -20
