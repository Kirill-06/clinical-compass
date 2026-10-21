"""Общие фикстуры API-тестов.

Демо-база создаётся один раз за сессию (миграции + сид), каждый тест
получает свою копию файла SQLite — тесты изолированы и быстры.
"""

import shutil
from collections.abc import Callable, Iterator
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import pytest
from fastapi.testclient import TestClient

from clinical_compass.api.runtime import Runtime
from clinical_compass.config import Settings
from clinical_compass.db.migrations import upgrade_to_head
from clinical_compass.domain.extraction import Extractor
from clinical_compass.main import create_app
from clinical_compass.seed import seed_if_empty
from clinical_compass.services.context import MemoryBlobStorage

FIXED_NOW = datetime(2026, 10, 21, 9, tzinfo=UTC)
INTERNAL_TOKEN = "test-internal-token"
CONTRACTS_DIR = Path(__file__).resolve().parents[2] / "contracts"


def make_settings(db_file: Path) -> Settings:
    return Settings(
        database_url=f"sqlite:///{db_file}",
        contracts_dir=CONTRACTS_DIR,
        storage_dir=db_file.parent / "files",
        internal_token=INTERNAL_TOKEN,
        fixed_now=FIXED_NOW,
        seed_demo_data=False,
    )


@pytest.fixture(scope="session")
def seeded_db(tmp_path_factory: pytest.TempPathFactory) -> Path:
    db_file = tmp_path_factory.mktemp("template") / "demo.sqlite"
    settings = make_settings(db_file)
    upgrade_to_head(settings.database_url)
    runtime = Runtime.build(settings, storage=_SHARED_STORAGE)
    with runtime.session_factory() as session:
        assert seed_if_empty(runtime.deps(session))
        session.commit()
    runtime.engine.dispose()
    return db_file


# Вложения демо-данных лежат в памяти и общие для всех копий базы.
_SHARED_STORAGE = MemoryBlobStorage()


@dataclass
class Api:
    """Тонкая обёртка над TestClient: вход демо-пользователем и разбор JSON."""

    client: TestClient
    tokens: dict[str, str] = field(default_factory=dict)

    def call(
        self,
        method: str,
        path: str,
        *,
        as_: str | None = None,
        body: Any = None,
        headers: dict[str, str] | None = None,
    ) -> tuple[int, Any]:
        h = dict(headers or {})
        if as_ is not None:
            h["Authorization"] = f"Bearer {self.token(as_)}"
        res = self.client.request(method, path, json=body, headers=h)
        is_json = "json" in res.headers.get("content-type", "") and res.content
        return res.status_code, res.json() if is_json else res.content

    def token(self, user_id: str) -> str:
        if user_id not in self.tokens:
            res = self.client.post("/auth/demo-login", json={"user_id": user_id})
            assert res.status_code == 200, res.text
            self.tokens[user_id] = res.json()["token"]
        return self.tokens[user_id]

    def queue(self, doctor: str) -> list[dict[str, Any]]:
        status, body = self.call("GET", "/doctor/queue", as_=doctor)
        assert status == 200
        return list(body)

    def internal(self, path: str, body: Any) -> tuple[int, Any]:
        return self.call("POST", path, body=body, headers={"X-Internal-Token": INTERNAL_TOKEN})


ApiFactory = Callable[..., Api]


@pytest.fixture
def make_api(seeded_db: Path, tmp_path: Path) -> Iterator[ApiFactory]:
    """Фабрика клиентов. `db_file` — переиспользовать базу (проверка перезапуска)."""
    clients: list[TestClient] = []

    def factory(*, extractor: Extractor | None = None, db_file: Path | None = None) -> Api:
        if db_file is None:
            db_file = tmp_path / f"db_{len(clients)}.sqlite"
            shutil.copy(seeded_db, db_file)
        settings = make_settings(db_file)
        runtime = Runtime.build(settings, extractor=extractor, storage=_SHARED_STORAGE)
        client = TestClient(create_app(settings, runtime))
        client.__enter__()
        clients.append(client)
        return Api(client)

    yield factory
    for client in clients:
        client.__exit__(None, None, None)


@pytest.fixture
def api(make_api: ApiFactory) -> Api:
    return make_api()


def rule_ids(queue: list[dict[str, Any]], patient_id: str) -> list[str]:
    return [a["alert"]["rule_id"] for a in queue if a["patient"]["id"] == patient_id]


def find_alert(queue: list[dict[str, Any]], rule_id: str, patient_id: str) -> dict[str, Any]:
    return next(a for a in queue if a["alert"]["rule_id"] == rule_id and a["patient"]["id"] == patient_id)
