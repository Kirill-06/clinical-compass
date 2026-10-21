"""Опросники и подсчёт баллов. Формулировки читаются из `contracts/instruments_v0.2.yaml`."""

from dataclasses import dataclass
from typing import Any

from clinical_compass.domain.enums import Instrument


@dataclass(frozen=True)
class AnswerOption:
    value: int
    label: str


@dataclass(frozen=True)
class SeverityBand:
    code: str
    min: int
    max: int
    label: str

    def contains(self, score: int) -> bool:
        return self.min <= score <= self.max


@dataclass(frozen=True)
class InstrumentDefinition:
    instrument: Instrument
    label: str
    version: str
    title: str
    instruction: str
    source: str
    wording_note: str | None
    items: tuple[str, ...]
    options: tuple[AnswerOption, ...]
    bands: tuple[SeverityBand, ...]

    @property
    def item_count(self) -> int:
        return len(self.items)

    @property
    def max_score(self) -> int:
        return self.item_count * max(o.value for o in self.options)

    def band_for(self, score: int) -> SeverityBand:
        for band in self.bands:
            if band.contains(score):
                return band
        raise ValueError(f"{self.label}: нет категории для {score} баллов")

    def to_json(self) -> dict[str, Any]:
        return {
            "instrument": self.instrument.value,
            "label": self.label,
            "version": self.version,
            "title": self.title,
            "instruction": self.instruction,
            "source": self.source,
            "wording_note": self.wording_note,
            "items": list(self.items),
            "options": [{"value": o.value, "label": o.label} for o in self.options],
            "bands": [{"code": b.code, "min": b.min, "max": b.max, "label": b.label} for b in self.bands],
            "item_count": self.item_count,
            "max_score": self.max_score,
        }


def parse_instruments(raw: dict[str, Any]) -> dict[Instrument, InstrumentDefinition]:
    """Разобрать YAML-определения шкал с проверкой целостности."""
    result: dict[Instrument, InstrumentDefinition] = {}
    for item in raw["instruments"]:
        definition = InstrumentDefinition(
            instrument=Instrument(item["code"]),
            label=item["label"],
            version=str(item["version"]),
            title=item["title"],
            instruction=item["instruction"],
            source=item["source"],
            wording_note=item.get("wording_note"),
            items=tuple(item["items"]),
            options=tuple(AnswerOption(int(o["value"]), o["label"]) for o in item["options"]),
            bands=tuple(
                SeverityBand(b["code"], int(b["min"]), int(b["max"]), b["label"]) for b in item["bands"]
            ),
        )
        covered = [
            s for s in range(definition.max_score + 1) if not any(b.contains(s) for b in definition.bands)
        ]
        if covered:
            raise ValueError(f"{definition.label}: категории не покрывают баллы {covered}")
        result[definition.instrument] = definition
    missing = set(Instrument) - result.keys()
    if missing:
        raise ValueError(f"Нет определений шкал: {sorted(missing)}")
    return result


class ScoringError(ValueError):
    """Неполный или некорректный набор ответов. Частичные анкеты не сохраняются."""


@dataclass(frozen=True)
class Score:
    total: int
    band: SeverityBand
    phq9_item9: int | None


def score_items(definition: InstrumentDefinition, items: list[int]) -> Score:
    if len(items) != definition.item_count:
        raise ScoringError(
            f"{definition.label}: нужно {definition.item_count} ответов, получено {len(items)}"
        )
    allowed = {o.value for o in definition.options}
    invalid = [v for v in items if v not in allowed]
    if invalid:
        raise ScoringError(f"{definition.label}: ответы вне шкалы: {invalid}")
    total = sum(items)
    return Score(
        total=total,
        band=definition.band_for(total),
        phq9_item9=items[8] if definition.instrument is Instrument.PHQ9 else None,
    )
