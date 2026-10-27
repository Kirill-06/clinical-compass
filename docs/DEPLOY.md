# Развёртывание

## Демо-стенд: https://my.onco-core.ru

На основном домене https://onco-core.ru — лендинг проекта (папка `landing/`, см. ниже).

Сервер команды (`ssh -p 2222 kirill@155.212.15.238`), по правилам сервера:

| Что | Где |
|---|---|
| Код и compose | `~/apps/clinical-compass/` |
| Секреты | `~/apps/clinical-compass/.env` (права 600, сгенерированы на сервере, в git не попадают) |
| Порт приложения | `127.0.0.1:8010` — наружу только через edge-caddy |
| Centrifugo (чат) | `127.0.0.1:8012`, снаружи — `wss://<домен>/connection/websocket` через тот же Caddy |
| Домен | `/etc/caddy/sites/onco-core.caddy`: `my.onco-core.ru` → приложение `127.0.0.1:8010`, `/connection/*` → Centrifugo; `onco-core.ru` → лендинг, старые ссылки на сервис (`/mis-demo.html`, `/docs`, `/integrations/*`) перенаправляются на `my.`; `compass.lamagate.com` тоже ведёт на `my.` |
| База | PostgreSQL в томе `clinical-compass_db-data`, вложения — `clinical-compass_files` |

### Обновить стенд

Из корня репозитория, на закоммиченном коде (обычно это `main`):

```bash
make deploy
```

Скрипт `scripts/deploy.sh` собирает Flutter Web на этой машине (около 20 секунд), отправляет на сервер код
текущего коммита и готовую сборку в `~/apps/clinical-compass/web-dist/`, а сервер собирает только
Python-часть образа (`WEB_SOURCE=web-prebuilt`) и перезапускает приложение. В конце скрипт ждёт ответа
`/health`. Если в `lib/`, `web/`, `backend/` или `contracts/` есть незакоммиченные правки, скрипт остановится:
код и веб должны быть из одного коммита.

Миграции применяются при старте контейнера; база, вложения и `.env` не трогаются.

Собирать Flutter на сервере не стоит: у него 4 ядра на два десятка сервисов, и сборка занимает больше
10 минут. Обычный `docker compose up --build` без `WEB_SOURCE` по-прежнему собирает веб внутри образа —
так работают CI и запуск одной командой из README.

### Проверить

```bash
curl -s https://my.onco-core.ru/health
```

```bash
ssh -p 2222 kirill@155.212.15.238 'cd ~/apps/clinical-compass && docker compose -p clinical-compass ps && docker compose -p clinical-compass logs --tail 50 app'
```

### Сбросить демо-данные

Удаляет базу стенда и заново заполняет её вымышленными данными:

```bash
ssh -p 2222 kirill@155.212.15.238 'cd ~/apps/clinical-compass && docker compose -p clinical-compass down -v && docker compose -p clinical-compass up -d'
```

## Лендинг: https://onco-core.ru

Статическая страница из `landing/` в контейнере nginx, `~/apps/onco-landing/`, порт `127.0.0.1:8013`.
Конфиг Caddy для обоих доменов — `landing/onco-core.caddy`.

Обновить:

```bash
make deploy-landing
```

Посмотреть локально: `python3 -m http.server 8090 --directory landing`.

## Переезд на onco-core.ru и включение чата (выполнено 26.10.2026)

С 27.10.2026 сервис живёт на `my.onco-core.ru`: в `.env` на сервере `PUBLIC_ORIGIN`, `CENTRIFUGO_PUBLIC_URL`
и `CC_CORS_ORIGINS` указывают на `my.onco-core.ru`.

Шаги ниже уже сделаны; оставлены как инструкция для другого домена. Конфиги Caddy лежат на сервере: `~/apps/clinical-compass/onco-core.caddy` (приложение и WebSocket
Centrifugo по пути `/connection/`) и обновлённый `compass.caddy` (старый адрес перенаправляет на новый).

1. **DNS.** У регистратора (Spaceweb) A-запись `onco-core.ru` → `155.212.15.238`. Запись `www` уже указывает туда.
   Проверка: `dig +short onco-core.ru` возвращает `155.212.15.238`.
2. **Секреты чата** — дописать в `~/apps/clinical-compass/.env` на сервере (генерируются там же):

   ```bash
   ssh -p 2222 kirill@155.212.15.238 'cd ~/apps/clinical-compass && umask 077 && printf "\nCENTRIFUGO_API_KEY=%s\nCENTRIFUGO_TOKEN_SECRET=%s\nCENTRIFUGO_PORT=8012\nPUBLIC_ORIGIN=https://onco-core.ru\nCENTRIFUGO_PUBLIC_URL=wss://onco-core.ru/connection/websocket\n" "$(openssl rand -hex 24)" "$(openssl rand -hex 32)" >> .env && sed -i "s|^CC_CORS_ORIGINS=.*|CC_CORS_ORIGINS=[\"https://onco-core.ru\"]|" .env'
   ```

3. **Обновить код** — команды из раздела «Обновить стенд» выше (поднимется и контейнер Centrifugo на `127.0.0.1:8012`).
4. **Домен** (нужен пароль `sudo`):

   ```bash
   ssh -t -p 2222 kirill@155.212.15.238 'sudo cp ~/apps/clinical-compass/onco-core.caddy ~/apps/clinical-compass/compass.caddy /etc/caddy/sites/ && docker exec edge-caddy caddy validate --config /etc/caddy/Caddyfile --adapter caddyfile && docker exec edge-caddy caddy reload --config /etc/caddy/Caddyfile --adapter caddyfile'
   ```

5. **Проверка:** `curl -s https://my.onco-core.ru/health`, затем в приложении у пациента во вкладке «Врач» горит
   «Сообщения приходят сразу».

## Любой другой сервер

Нужны Docker и обратный прокси с HTTPS (Caddy, nginx). Приложение публикует порт только на `127.0.0.1`.

```bash
cp .env.example .env
```

Задайте в `.env` пароль базы, `CC_INTERNAL_TOKEN`, `CC_INTEGRATION_KEYS`, `APP_PORT` и `CC_CORS_ORIGINS`, затем:

```bash
docker compose up -d --build
```
