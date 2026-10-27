#!/usr/bin/env bash
# Выкатка стенда my.onco-core.ru: Flutter Web собирается здесь, на сервер уходит готовая сборка,
# а сервер собирает только Python-часть образа. Подробности — docs/DEPLOY.md.
#
#   ./scripts/deploy.sh            сервис (код текущего коммита + веб)
#   ./scripts/deploy.sh landing    лендинг onco-core.ru
set -Eeuo pipefail

repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
host="${DEPLOY_HOST:-kirill@155.212.15.238}"
port="${DEPLOY_PORT:-2222}"
app_dir="${DEPLOY_APP_DIR:-apps/clinical-compass}"
landing_dir="${DEPLOY_LANDING_DIR:-apps/onco-landing}"
public_url="${DEPLOY_PUBLIC_URL:-https://my.onco-core.ru}"
ssh_opts=(-p "$port" -o ServerAliveInterval=60 -o ServerAliveCountMax=5)

cd "$repo_root"

# Если первый в PATH git не запускается (например, старая сборка под Intel без Rosetta),
# берём системный — он нужен и этому скрипту, и Flutter.
if ! git --version >/dev/null 2>&1; then
  if /usr/bin/git --version >/dev/null 2>&1; then
    export PATH="/usr/bin:$PATH"
  else
    echo 'Не запускается git. Проверьте, какой git первый в PATH: command -v git' >&2
    exit 1
  fi
fi

remote() { ssh "${ssh_opts[@]}" "$host" "$@"; }

deploy_landing() {
  echo '→ Лендинг'
  rsync -az --delete --exclude '*.bak' -e "ssh ${ssh_opts[*]}" landing/ "$host:$landing_dir/"
  remote "cd ~/$landing_dir && docker compose -p onco-landing up -d --build"
}

deploy_app() {
  # Код и веб должны быть из одного коммита: незакоммиченные правки не выкатываем.
  local dirty
  dirty="$(git status --porcelain -- lib web backend contracts pubspec.yaml pubspec.lock Dockerfile docker-compose.yml)"
  if [[ -n "$dirty" ]]; then
    echo 'Есть незакоммиченные изменения — закоммитьте их или уберите перед выкаткой.' >&2
    exit 1
  fi
  local commit
  commit="$(git rev-parse --short HEAD)"

  echo "→ Flutter Web ($commit)"
  flutter build web --release --no-web-resources-cdn

  echo '→ Код на сервер'
  git archive --format=tar HEAD | remote "tar -x -C ~/$app_dir"

  echo '→ Веб-сборка на сервер'
  rsync -az --delete -e "ssh ${ssh_opts[*]}" build/web/ "$host:$app_dir/web-dist/"

  echo '→ Сборка образа и перезапуск (база и вложения не трогаются)'
  remote "cd ~/$app_dir && WEB_SOURCE=web-prebuilt docker compose -p clinical-compass up -d --build app"

  echo "→ Проверка $public_url/health"
  for _ in $(seq 1 30); do
    if curl -fs -o /dev/null --max-time 5 "$public_url/health"; then
      echo "Готово: $public_url ($commit)"
      return
    fi
    sleep 2
  done
  echo 'Сервис не ответил за минуту. Логи: docker compose -p clinical-compass logs --tail 50 app' >&2
  exit 1
}

case "${1:-app}" in
  app) deploy_app ;;
  landing) deploy_landing ;;
  *) echo "Неизвестная цель: $1 (app | landing)" >&2; exit 1 ;;
esac
