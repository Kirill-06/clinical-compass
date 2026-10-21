"""Демо-вход и текущий пользователь."""

from typing import Any

from fastapi import APIRouter

from clinical_compass.api.deps import DepsDep, PrincipalDep, RuntimeDep
from clinical_compass.api.schemas import DemoLoginRequest
from clinical_compass.services.auth import AuthService
from clinical_compass.services.errors import NotFoundError

router = APIRouter(tags=["auth"])


def _require_demo(runtime: RuntimeDep) -> None:
    if not runtime.settings.demo_auth:
        raise NotFoundError("Демо-вход отключён")


@router.get("/demo/accounts")
def demo_accounts(deps: DepsDep, runtime: RuntimeDep) -> dict[str, Any]:
    _require_demo(runtime)
    return AuthService(deps).demo_accounts()


@router.post("/auth/demo-login")
def demo_login(body: DemoLoginRequest, deps: DepsDep, runtime: RuntimeDep) -> dict[str, Any]:
    _require_demo(runtime)
    token, principal = AuthService(deps, runtime.settings.session_ttl_hours).login(body.user_id)
    return {"token": token, "user": principal.to_json(), "demo": True}


@router.get("/me")
def me(principal: PrincipalDep) -> dict[str, str]:
    return principal.to_json()
