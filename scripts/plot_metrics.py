"""Графики для слайда «Метрики» из сохранённых результатов оценки AI-извлечения.

Каждая цифра на графиках берётся из evaluation/results/*.json — их можно перепроверить.
Запуск из корня репозитория:

    uv run --with matplotlib python scripts/plot_metrics.py
"""

import json
from pathlib import Path

import matplotlib as mpl
import matplotlib.pyplot as plt

ROOT = Path(__file__).resolve().parents[1]
RESULTS = ROOT / "evaluation" / "results"
OUT = ROOT / "docs" / "presentation"

INK = "#17212B"
MUTED = "#5A6872"
GRID = "#E3E8EB"
TEAL = "#0D5966"
TEAL_LIGHT = "#7FB8C1"
AMBER = "#E0A33A"
CORAL = "#D9644A"
GREEN = "#2E8B57"

mpl.rcParams.update(
    {
        "font.family": "DejaVu Sans",
        "font.size": 12,
        "axes.edgecolor": GRID,
        "axes.labelcolor": MUTED,
        "xtick.color": MUTED,
        "ytick.color": INK,
        "axes.titleweight": "bold",
        "axes.titlesize": 15,
        "axes.titlecolor": INK,
        "axes.spines.top": False,
        "axes.spines.right": False,
        "figure.dpi": 100,
        "savefig.dpi": 220,
        "savefig.bbox": "tight",
        "savefig.facecolor": "white",
    }
)


def load(version: str) -> dict:
    return json.loads((RESULTS / f"gigachat_v{version}.json").read_text(encoding="utf-8"))


def pct(value: float) -> str:
    return f"{round(value * 100)}%"


def seconds(ms: float) -> str:
    """1843.8 мс → «1,8 с» (десятичная запятая, как принято в русском тексте)."""
    return f"{ms / 1000:.1f}".replace(".", ",") + " с"


def entity_quality(v12: dict) -> None:
    """Точность, полнота и F1 по каждому типу сущностей (v1.2)."""
    names = {
        "symptom": "Симптомы",
        "medication": "Приём\nпрепарата",
        "risk_signal": "Сигналы\nриска",
        "lab_mention": "Анализы",
    }
    per_type = v12["per_entity_type"]
    labels = [f"{names[k]}\n(n={per_type[k]['tp'] + per_type[k]['fn']})" for k in names]
    series = [("Точность", "precision", TEAL_LIGHT), ("Полнота", "recall", TEAL), ("F1", "f1", AMBER)]

    fig, ax = plt.subplots(figsize=(7.2, 4.6))
    width = 0.26
    for i, (title, key, color) in enumerate(series):
        xs = [x + (i - 1) * width for x in range(len(names))]
        values = [per_type[k][key] for k in names]
        bars = ax.bar(xs, values, width, label=title, color=color)
        ax.bar_label(bars, labels=[pct(v) for v in values], padding=2, fontsize=9, color=INK)
    ax.set_xticks(range(len(names)), labels)
    ax.set_ylim(0, 1.12)
    ax.yaxis.set_major_formatter(mpl.ticker.PercentFormatter(1.0))
    ax.grid(axis="y", color=GRID)
    ax.set_axisbelow(True)
    ax.legend(frameon=False, ncols=3, loc="upper left")
    ax.set_title("Качество извлечения по типам фактов")
    fig.text(0, -0.1, "155 сообщений, 172 размеченных факта · GigaChat, промпт v1.2", color=MUTED, fontsize=10)
    fig.savefig(OUT / "metrics_by_entity.png")
    plt.close(fig)


def prompt_tuning(v11: dict, v12: dict) -> None:
    """Что дала настройка промпта под безопасность: v1.1 → v1.2."""
    rows = [
        ("Полнота сигналов риска", v11["risk_recall"], v12["risk_recall"]),
        ("F1 сигналов риска", v11["per_entity_type"]["risk_signal"]["f1"], v12["per_entity_type"]["risk_signal"]["f1"]),
        ("Полнота, все факты", v11["overall"]["recall"], v12["overall"]["recall"]),
        ("F1, все факты", v11["overall"]["f1"], v12["overall"]["f1"]),
    ]
    fig, ax = plt.subplots(figsize=(7.2, 4.6))
    ys = list(range(len(rows)))[::-1]
    height = 0.36
    before = ax.barh([y + height / 2 for y in ys], [r[1] for r in rows], height, color="#C9D3D8", label="v1.1")
    after = ax.barh([y - height / 2 for y in ys], [r[2] for r in rows], height, color=TEAL, label="v1.2")
    ax.bar_label(before, labels=[pct(r[1]) for r in rows], padding=3, fontsize=10, color=MUTED)
    ax.bar_label(after, labels=[pct(r[2]) for r in rows], padding=3, fontsize=10, color=INK, fontweight="bold")
    ax.set_yticks(ys, [r[0] for r in rows])
    ax.set_xlim(0, 1.12)
    ax.xaxis.set_major_formatter(mpl.ticker.PercentFormatter(1.0))
    ax.grid(axis="x", color=GRID)
    ax.set_axisbelow(True)
    ax.legend(frameon=False, loc="lower right")
    ax.set_title("Настройка промпта под безопасность")
    risk11, risk12 = v11["per_entity_type"]["risk_signal"], v12["per_entity_type"]["risk_signal"]
    gold = risk12["tp"] + risk12["fn"]
    fig.text(
        0,
        -0.02,
        f"Найдено сигналов риска: {risk11['tp']} из {gold} → {risk12['tp']} из {gold} · "
        f"P95 ответа: {seconds(v11['latency_ms']['p95'])} → {seconds(v12['latency_ms']['p95'])}",
        color=MUTED,
        fontsize=10,
    )
    fig.savefig(OUT / "metrics_prompt_tuning.png")
    plt.close(fig)


def key_indicators(v12: dict) -> None:
    """Главные показатели надёжности контура AI (v1.2)."""
    overall = v12["overall"]
    rows = [
        ("Ответ по схеме", v12["schema_pass_rate"], GREEN),
        ("Полнота сигналов риска", v12["risk_recall"], CORAL),
        ("Полнота", overall["recall"], TEAL),
        ("F1", overall["f1"], TEAL_LIGHT),
        ("Точность", overall["precision"], TEAL_LIGHT),
    ]
    fig, ax = plt.subplots(figsize=(7.2, 4.6))
    ys = list(range(len(rows)))[::-1]
    bars = ax.barh(ys, [r[1] for r in rows], 0.6, color=[r[2] for r in rows])
    ax.bar_label(bars, labels=[pct(r[1]) for r in rows], padding=4, fontsize=11, color=INK, fontweight="bold")
    ax.set_yticks(ys, [r[0] for r in rows])
    ax.set_xlim(0, 1.15)
    ax.xaxis.set_major_formatter(mpl.ticker.PercentFormatter(1.0))
    ax.grid(axis="x", color=GRID)
    ax.set_axisbelow(True)
    ax.set_title("Ключевые показатели AI-извлечения")
    latency = v12["latency_ms"]
    fig.text(
        0,
        -0.02,
        f"Сбоев: {v12['failed_messages']} из {v12['dataset']['messages']} сообщений · "
        f"ответ: медиана {seconds(latency['p50'])}, P95 {seconds(latency['p95'])} · "
        "при сбое AI красные флаги ловит встроенный словарь",
        color=MUTED,
        fontsize=10,
    )
    fig.savefig(OUT / "metrics_key_indicators.png")
    plt.close(fig)


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    v11, v12 = load("1_1"), load("1_2")
    entity_quality(v12)
    prompt_tuning(v11, v12)
    key_indicators(v12)
    print("Графики сохранены в", OUT.relative_to(ROOT))


if __name__ == "__main__":
    main()
