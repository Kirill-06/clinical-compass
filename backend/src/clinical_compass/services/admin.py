"""Администратор записи: только контакт и срок, без клинических данных (§15)."""

from clinical_compass.domain.enums import BookingStatus, Role
from clinical_compass.services.access import AccessPolicy
from clinical_compass.services.context import Deps, Principal
from clinical_compass.services.errors import NotFoundError
from clinical_compass.services.presenter import Json, Presenter


class AdminService:
    def __init__(self, deps: Deps) -> None:
        self._d = deps
        self._access = AccessPolicy(deps)
        self._present = Presenter(deps)

    def tasks(self, principal: Principal) -> list[Json]:
        self._access.require_role(principal, Role.ADMIN, "Список задач доступен администратору")
        return [self._present.booking(t) for t in self._d.repos.bookings.all()]

    def update(self, principal: Principal, task_id: str, status: BookingStatus) -> Json:
        self._access.require_role(principal, Role.ADMIN, "Изменять задачи может администратор")
        task = self._d.repos.bookings.get(task_id)
        if task is None:
            raise NotFoundError("Задача не найдена")
        task.status = status.value
        task.updated_at = self._d.clock.now()
        self._d.audit(principal, f"booking.{status.value}", "booking", task.id, task.patient_id)
        return self._present.booking(task)
