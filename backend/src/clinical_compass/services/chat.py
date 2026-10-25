"""Переписка пациента с лечащим врачом.

Сообщения пациента по-прежнему проходят через `PatientService.send_message`:
сохраняются до обработки ИИ, из них извлекаются факты и красные флаги. Здесь —
лента переписки, ответ врача и отметки «прочитано». Чат не экстренный канал:
врач отвечает в рабочее время, а срочные случаи идут через очередь и экран 112.
"""

from datetime import timedelta

from clinical_compass.db.models import MessageRow
from clinical_compass.domain.enums import Role
from clinical_compass.services.access import AccessPolicy
from clinical_compass.services.context import Deps, Principal, new_id
from clinical_compass.services.errors import ForbiddenError, InvalidInputError
from clinical_compass.services.presenter import Json, Presenter
from clinical_compass.services.realtime import Realtime, chat_channel, queue_channel

PATIENT, DOCTOR = "patient", "doctor"


class ChatService:
    def __init__(self, deps: Deps) -> None:
        self._d = deps
        self._access = AccessPolicy(deps)
        self._present = Presenter(deps)

    def thread(self, principal: Principal, patient_id: str) -> Json:
        """Вся переписка по порядку. Только чтение: «прочитано» отмечает `mark_read`."""
        self._access.require_read(principal, patient_id)
        messages = self._present.messages(patient_id, for_patient=principal.role is Role.PATIENT)
        return {"patient_id": patient_id, "messages": list(reversed(messages))}

    def mark_read(self, principal: Principal, patient_id: str) -> Json:
        """Отметить прочитанными сообщения собеседника — когда переписка действительно на экране."""
        self._access.require_read(principal, patient_id)
        counterpart = DOCTOR if principal.role is Role.PATIENT else PATIENT
        marked = self._d.repos.messages.mark_read(patient_id, sender=counterpart, at=self._d.clock.now())
        if marked:
            self._d.notify(chat_channel(patient_id), "read", reader=principal.role.value)
        return {"marked": marked}

    def doctor_reply(self, principal: Principal, patient_id: str, text: str) -> Json:
        self._access.require_doctor_for(principal, patient_id)
        body = text.strip()
        if not body:
            raise InvalidInputError("Напишите сообщение")
        if len(body) > self._d.limits.max_text_length:
            raise InvalidInputError(f"Сообщение длиннее {self._d.limits.max_text_length} символов")
        message = MessageRow(
            id=new_id("msg"),
            patient_id=patient_id,
            sender=DOCTOR,
            recipient_doctor_id=principal.user_id,
            text=body,
            created_at=self._d.clock.now(),
            extraction_status="not_applicable",
            clarifying_questions=[],
        )
        self._d.repos.messages.add(message)
        self._d.audit(principal, "message.doctor_reply", "message", message.id, patient_id)
        self._d.notify(chat_channel(patient_id), "message", message_id=message.id, sender=DOCTOR)
        return {"message": self._present.message(message, [], for_patient=False)}

    def connection(self, principal: Principal, realtime: Realtime, ttl: timedelta) -> Json:
        """Подключение к Centrifugo: адрес и токен со списком разрешённых каналов."""
        if principal.role is Role.ADMIN:
            raise ForbiddenError("Чат доступен пациенту и врачу")
        if not realtime.enabled or realtime.public_url is None:
            return {"enabled": False}
        if principal.role is Role.PATIENT:
            channels = [chat_channel(principal.user_id)]
        else:
            patients = self._access.doctor_patient_ids(principal)
            channels = [queue_channel(principal.user_id), *(chat_channel(p) for p in patients)]
        return {
            "enabled": True,
            "url": realtime.public_url,
            "token": realtime.connection_token(principal.user_id, channels, ttl),
            "channels": channels,
        }
