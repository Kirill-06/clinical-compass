#!/usr/bin/env bash
set -Eeuo pipefail

repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
web_dir="$repo_root/build/web"

if ! command -v uv >/dev/null 2>&1; then
  echo 'Нужен uv. См. README.md → Быстрый старт.' >&2
  exit 1
fi
if [[ ! -f "$web_dir/index.html" ]]; then
  echo 'Нет build/web/index.html. Из корня проекта выполните: make web' >&2
  exit 1
fi
if [[ -z "${AI_API_KEY:-}" ]]; then
  echo 'Задайте AI_API_KEY: действующий access token GigaChat (не Authorization Key).' >&2
  exit 1
fi
if [[ -z "${AI_BASE_URL:-}" ]]; then
  echo 'Задайте AI_BASE_URL: адрес OpenAI-compatible API GigaChat с суффиксом /v1.' >&2
  exit 1
fi
if [[ -n "${SSL_CERT_FILE:-}" && ! -r "$SSL_CERT_FILE" ]]; then
  echo 'Файл SSL_CERT_FILE недоступен для чтения.' >&2
  exit 1
fi
if ! command -v curl >/dev/null 2>&1; then
  echo 'Для проверки сервисов нужен curl.' >&2
  exit 1
fi

cp "$repo_root/web/mis-demo.html" "$web_dir/mis-demo.html"
log_dir="$(mktemp -d)"
ai_pid=''
backend_pid=''
cleanup() {
  trap - EXIT INT TERM
  [[ -z "$backend_pid" ]] || kill "$backend_pid" 2>/dev/null || true
  [[ -z "$ai_pid" ]] || kill "$ai_pid" 2>/dev/null || true
  [[ -z "$backend_pid" ]] || wait "$backend_pid" 2>/dev/null || true
  [[ -z "$ai_pid" ]] || wait "$ai_pid" 2>/dev/null || true
  rm -rf "$log_dir"
}
trap cleanup EXIT
trap 'exit 130' INT
trap 'exit 143' TERM

(
  cd "$repo_root/ai_service"
  export AI_MODEL=GigaChat-3-Ultra
  exec uv run uvicorn clinical_compass_ai.main:app --host 127.0.0.1 --port 8090
) >"$log_dir/ai.log" 2>&1 &
ai_pid=$!

wait_for_health() {
  local name="$1" url="$2" pid="$3"
  for ((attempt=0; attempt<60; attempt++)); do
    if curl --silent --fail --max-time 2 "$url" >/dev/null; then
      return 0
    fi
    if ! kill -0 "$pid" 2>/dev/null; then break; fi
    sleep 1
  done
  echo "$name не запустился. Проверьте зависимости, настройки и доступность портов." >&2
  return 1
}
wait_for_health 'AI service' 'http://127.0.0.1:8090/health' "$ai_pid"

(
  cd "$repo_root/backend"
  export CC_WEB_DIR="$web_dir"
  export CC_EXTRACTOR_MODE=remote
  export CC_EXTRACTOR_URL=http://127.0.0.1:8090/extract
  exec uv run clinical-compass serve --host 127.0.0.1 --port 8080
) >"$log_dir/backend.log" 2>&1 &
backend_pid=$!
wait_for_health 'Backend' 'http://127.0.0.1:8080/health' "$backend_pid"

printf '%s\n' 'http://127.0.0.1:8080/' 'http://127.0.0.1:8080/mis-demo.html'
while kill -0 "$ai_pid" 2>/dev/null && kill -0 "$backend_pid" 2>/dev/null; do sleep 1; done
echo 'Один из сервисов завершился. Перезапустите стенд после проверки настроек.' >&2
exit 1
