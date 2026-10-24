# Развёртывание

## Демо-стенд: https://compass.lamagate.com

Сервер команды (`ssh -p 2222 kirill@155.212.15.238`), по правилам сервера:

| Что | Где |
|---|---|
| Код и compose | `~/apps/clinical-compass/` |
| Секреты | `~/apps/clinical-compass/.env` (права 600, сгенерированы на сервере, в git не попадают) |
| Порт приложения | `127.0.0.1:8010` — наружу только через edge-caddy |
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

## Любой другой сервер

Нужны Docker и обратный прокси с HTTPS (Caddy, nginx). Приложение публикует порт только на `127.0.0.1`.

```bash
cp .env.example .env
```

Задайте в `.env` пароль базы, `CC_INTERNAL_TOKEN`, `CC_INTEGRATION_KEYS`, `APP_PORT` и `CC_CORS_ORIGINS`, затем:

```bash
docker compose up -d --build
```
