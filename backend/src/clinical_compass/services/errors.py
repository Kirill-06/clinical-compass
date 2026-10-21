"""Ошибки сценариев. HTTP-статус назначает слой API (`api/errors.py`)."""


class ServiceError(Exception):
    """Базовая ошибка с понятным пользователю текстом."""

    def __init__(self, message: str) -> None:
        super().__init__(message)
        self.message = message


class NotFoundError(ServiceError):
    pass


class ForbiddenError(ServiceError):
    pass


class UnauthorizedError(ServiceError):
    pass


class ConflictError(ServiceError):
    pass


class InvalidInputError(ServiceError):
    pass
