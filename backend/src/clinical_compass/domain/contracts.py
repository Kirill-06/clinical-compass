"""Версионированные контракты v0.2 из каталога `contracts/`.

Всё, что меняется решением команды, а не кодом: правила, тексты пациенту,
формулировки шкал, подписи справочников, JSON Schema. Загрузка проверяет
согласованность — приложение не стартует с битым конфигом.
"""

import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml
from jsonschema import Draft202012Validator

from clinical_compass.domain.enums import Instrument
from clinical_compass.domain.instruments import InstrumentDefinition, parse_instruments
from clinical_compass.domain.rules import RuleSet


class ContractError(ValueError):
    """Контракты несогласованы или повреждены."""


@dataclass(frozen=True)
class PatientTemplate:
    id: str
    status: str
    """`approved` | `draft` — черновики помечаются в интерфейсе."""
    title: str
    body: str

    def to_json(self) -> dict[str, str]:
        return {"id": self.id, "status": self.status, "title": self.title, "body": self.body}


@dataclass(frozen=True)
class Contracts:
    rules: RuleSet
    templates: dict[str, PatientTemplate]
    templates_version: str
    instruments: dict[Instrument, InstrumentDefinition]
    vocabulary: dict[str, dict[str, str]]
    schema_validator: Draft202012Validator

    def template(self, template_id: str | None) -> PatientTemplate | None:
        return self.templates.get(template_id) if template_id else None

    def label(self, group: str, key: str | None) -> str | None:
        return self.vocabulary.get(group, {}).get(key) if key else None

    def rule_title(self, rule_id: str) -> str:
        return self.vocabulary.get("rule_titles", {}).get(rule_id, rule_id)

    def schema_errors(self, document: dict[str, Any]) -> list[str]:
        """Ошибки проверки документа по patient_state_v0.2.schema.json."""
        return [
            f"{'/'.join(str(p) for p in e.absolute_path) or '<root>'}: {e.message}"
            for e in self.schema_validator.iter_errors(document)
        ]


class _Yaml12Loader(yaml.SafeLoader):
    """SafeLoader с булевыми значениями YAML 1.2: только true/false.

    PyYAML по умолчанию следует YAML 1.1 и превращает `yes`/`no` в булевы,
    а в правилах v0.2 это строковые значения (`affects_daily_life: yes`).
    """


_Yaml12Loader.yaml_implicit_resolvers = {
    key: [(tag, regexp) for tag, regexp in resolvers if tag != "tag:yaml.org,2002:bool"]
    for key, resolvers in yaml.SafeLoader.yaml_implicit_resolvers.items()
}
_Yaml12Loader.add_implicit_resolver(
    "tag:yaml.org,2002:bool", re.compile(r"^(?:true|True|TRUE|false|False|FALSE)$"), list("tTfF")
)


def parse_yaml(text: str) -> Any:
    return yaml.load(text, Loader=_Yaml12Loader)


def _yaml(path: Path) -> Any:
    try:
        return parse_yaml(path.read_text(encoding="utf-8"))
    except (OSError, yaml.YAMLError) as exc:
        raise ContractError(f"{path.name}: {exc}") from exc


def load_contracts(directory: Path) -> Contracts:
    rules = RuleSet.parse(_yaml(directory / "alert_rules_v0.2.yaml"))
    templates_raw = _yaml(directory / "patient_templates_v0.2.draft.yaml")
    templates = {
        t["id"]: PatientTemplate(
            id=t["id"],
            status=t.get("status", "draft"),
            title=t["title"],
            body=" ".join(str(t["body"]).split()),
        )
        for t in templates_raw["templates"]
    }
    missing = sorted({r.message_template_id for r in rules.rules if r.message_template_id} - templates.keys())
    if missing:
        raise ContractError(f"В реестре шаблонов нет: {missing}")
    schema = json.loads((directory / "patient_state_v0.2.schema.json").read_text(encoding="utf-8"))
    Draft202012Validator.check_schema(schema)
    vocabulary = _yaml(directory / "vocabulary_v0.2.yaml")
    unknown_titles = {r.id for r in rules.rules} - vocabulary.get("rule_titles", {}).keys()
    if unknown_titles:
        raise ContractError(f"Нет названий правил: {sorted(unknown_titles)}")
    return Contracts(
        rules=rules,
        templates=templates,
        templates_version=str(templates_raw.get("version", "unknown")),
        instruments=parse_instruments(_yaml(directory / "instruments_v0.2.yaml")),
        vocabulary={k: v for k, v in vocabulary.items() if isinstance(v, dict)},
        schema_validator=Draft202012Validator(schema),
    )
