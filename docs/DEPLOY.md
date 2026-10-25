# Развёртывание

## Демо-стенд: https://compass.lamagate.com

Сервер команды (`ssh -p 2222 kirill@155.212.15.238`), по правилам сервера:

| Что | Где |
|---|---|
| Код и compose | `~/apps/clinical-compass/` |
| Секреты | `~/apps/clinical-compass/.env` (права 600, сгенерированы на сервере, в git не попадают) |
| Порт приложения | `127.0.0.1:8010` — наружу только через edge-caddy |
| Centrifugo (чат) | `127.0.0.1:8012`, снаружи — `wss://<домен>/connection/websocket` через тот же Caddy |
| Домен | `/etc/caddy/sites/compass.caddy` → `reverse_proxy 127.0.0.1:8010` |
| База | PostgreSQL в томе `clinical-compass_db-data`, вложения — `clinical-compass_files` |

### Обновить стенд до текущего `main`

С компьютера разработчика, из корня репозитория:

```bash
git archive --format=tar origin/main | ssh -p 2222 kirill@155.212.15.238 'tar -x -C ~/apps/clinical-compass'
```

```bash
ssh -p 2222 kirill@155.212.15.238 'cd ~/apps/clinical-compass && docker compose -p clinical-compass up -d --build'
```

Миграции применяются при старте контейнера; `.env` архив не трогает.

### Проверить

```bash
curl -s https://compass.lamagate.com/health
```

```bash
ssh -p 2222 kirill@155.212.15.238 'cd ~/apps/clinical-compass && docker compose -p clinical-compass ps && docker compose -p clinical-compass logs --tail 50 app'
```

### Сбросить демо-данные

Удаляет базу стенда и заново заполняет её вымышленными данными:

```bash
ssh -p 2222 kirill@155.212.15.238 'cd ~/apps/clinical-compass && docker compose -p clinical-compass down -v && docker compose -p clinical-compass up -d'
```

## Переезд на onco-core.ru и включение чата

Конфиги Caddy уже лежат на сервере: `~/apps/clinical-compass/onco-core.caddy` (приложение и WebSocket
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

5. **Проверка:** `curl -s https://onco-core.ru/health`, затем в приложении у пациента во вкладке «Врач» горит
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
