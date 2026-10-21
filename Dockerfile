# syntax=docker/dockerfile:1.7
# Один образ: API (FastAPI) + собранный Flutter Web, отдаваемый с того же адреса.

# --- 1. Flutter Web ---------------------------------------------------------------------------
FROM ghcr.io/cirruslabs/flutter:3.44.0 AS web
WORKDIR /src
COPY pubspec.yaml pubspec.lock analysis_options.yaml ./
RUN flutter pub get
COPY lib lib
COPY web web
RUN flutter build web --release --no-web-resources-cdn

# --- 2. Python-зависимости и пакет ---------------------------------------------------------------
FROM python:3.12-slim AS backend-build
COPY --from=ghcr.io/astral-sh/uv:0.11.14 /uv /bin/uv
ENV UV_COMPILE_BYTECODE=1 UV_LINK_MODE=copy UV_PYTHON_DOWNLOADS=never
WORKDIR /app
COPY backend/pyproject.toml backend/uv.lock backend/README.md ./
RUN --mount=type=cache,target=/root/.cache/uv uv sync --frozen --no-dev --no-install-project
COPY backend/src src
RUN --mount=type=cache,target=/root/.cache/uv uv sync --frozen --no-dev --no-editable

# --- 3. Runtime --------------------------------------------------------------------------------
FROM python:3.12-slim AS runtime
RUN groupadd --system app && useradd --system --gid app --home /app app \
    && mkdir -p /data/files && chown -R app:app /data
WORKDIR /app
COPY --from=backend-build /app/.venv /app/.venv
COPY contracts /app/contracts
COPY --from=web /src/build/web /app/web
ENV PATH="/app/.venv/bin:$PATH" \
    PYTHONUNBUFFERED=1 \
    CC_CONTRACTS_DIR=/app/contracts \
    CC_WEB_DIR=/app/web \
    CC_STORAGE_DIR=/data/files \
    CC_DATABASE_URL=sqlite:////data/clinical_compass.db
USER app
EXPOSE 8080
HEALTHCHECK --interval=10s --timeout=3s --start-period=20s --retries=5 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8080/health', timeout=2)"
CMD ["clinical-compass", "serve", "--host", "0.0.0.0", "--port", "8080"]
