"""Compose two silent, captioned Full HD demos from Playwright screenshots."""

from __future__ import annotations

import subprocess
from dataclasses import dataclass
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont


ROOT = Path(__file__).resolve().parents[2]
ART = ROOT / "artifacts/demo"
FRAMES = ART / "frames"
SLIDES = ART / "slides"
SLIDES.mkdir(parents=True, exist_ok=True)
FONT = "/usr/share/fonts/TTF/FiraSans-Regular.ttf"
BOLD = "/usr/share/fonts/TTF/FiraSans-Bold.ttf"


@dataclass(frozen=True)
class Scene:
    name: str
    source: str
    title: str
    body: str
    crop: tuple[int, int, int, int] | None = None
    kind: str = "phone"


SCENES = {
    "entry": Scene("entry", "01-entry", "Связь между\nвизитами", "Пациент и врач работают в одном приложении. В видео — только вымышленные демо-данные.", kind="desktop"),
    "progress": Scene("progress", "02-progress", "Мой прогресс", "Новый блок v0.3 показывает дни с записями за неделю. Это регулярность ведения дневника, не оценка здоровья.", (0, 0, 1000, 1130)),
    "support": Scene("support", "02-progress", "Подсказка без давления", "Нейтральное сообщение можно скрыть. За ответы и показатели здоровья баллы не начисляются.", (0, 285, 1000, 1080)),
    "medication": Scene("medication", "03-medication", "Приём препарата", "Утро и вечер отмечаются отдельно. Пропуск можно указать честно, а схему лечения меняет только врач.", (0, 760, 1000, 1550)),
    "symptom": Scene("symptom", "04-symptom", "Самочувствие", "Пациент выбирает симптом и при необходимости описывает его своими словами. Запись передаётся врачу.", (0, 0, 1000, 1250)),
    "symptom_detail": Scene("symptom_detail", "05-symptom-detail", "Что беспокоит", "Форма уточняет влияние на обычные дела и выраженность симптома. Клиническое решение остаётся за врачом.", (0, 360, 1000, 1460)),
    "message": Scene("message", "07-risk-message", "Сообщение врачу", "Свободный текст сохраняется и передаётся врачу. Демонстрационный сигнал риска запускает правило и экран помощи.", (0, 720, 1000, 1780)),
    "emergency": Scene("emergency", "08-emergency", "Нужна срочная помощь?", "При сигнале самоповреждения пациент сразу видит 112 и 103. Врач получает событие в рабочей очереди.", (0, 0, 1000, 1060)),
    "queue": Scene("queue", "09-doctor-queue", "Очередь врача", "Срочные события закреплены до принятия в работу. Врач видит данные пациента и статус его действий.", (380, 0, 2160, 1220), "desktop"),
    "reason": Scene("reason", "10-alert-reason", "Почему этот алерт?", "Показаны правило, версия, источник и факты Patient State. Приоритет задают детерминированные правила.", (380, 0, 2160, 1100), "desktop"),
    "mis_select": Scene("mis_select", "11-mis-selection", "Демо-МИС", "Имитация медкарты показывает запуск из ЕМИАС или 1С:Медицина. Это демонстрационный стенд.", (0, 0, 2160, 1350), "desktop"),
    "mis_open": Scene("mis_open", "12-mis-open", "Карточка в МИС", "Карточка открывается внутри демо-медкарты по одноразовому коду — без отдельного входа врача.", (280, 0, 2160, 1350), "desktop"),
}


def wrap(draw: ImageDraw.ImageDraw, text: str, font: ImageFont.FreeTypeFont, width: int) -> list[str]:
    lines: list[str] = []
    for para in text.split("\n"):
        current = ""
        for word in para.split():
            trial = f"{current} {word}".strip()
            if draw.textlength(trial, font=font) <= width:
                current = trial
            else:
                if current:
                    lines.append(current)
                current = word
        lines.append(current)
    return lines


def render(scene: Scene) -> Path:
    canvas = Image.new("RGB", (1920, 1080), "#f3f7f7")
    draw = ImageDraw.Draw(canvas)
    draw.rounded_rectangle((0, 0, 1920, 15), fill="#0b6170", radius=0)
    draw.rounded_rectangle((84, 65, 134, 115), fill="#0b6170", radius=13)
    draw.polygon([(109, 72), (118, 90), (109, 108), (100, 90)], fill="white")
    draw.ellipse((106, 87, 112, 93), fill="#0b6170")
    draw.text((153, 71), "Клинический компас", font=ImageFont.truetype(BOLD, 28), fill="#17252d")
    draw.text((84, 173), "ДЕМОНСТРАЦИЯ  ·  V0.3", font=ImageFont.truetype(BOLD, 22), fill="#0b6170")
    title_font = ImageFont.truetype(BOLD, 66)
    body_font = ImageFont.truetype(FONT, 31)
    left_width = 650 if scene.kind == "phone" else 500
    y = 256
    for line in wrap(draw, scene.title, title_font, left_width):
        draw.text((84, y), line, font=title_font, fill="#17252d")
        y += 76
    y += 34
    for line in wrap(draw, scene.body, body_font, left_width):
        draw.text((84, y), line, font=body_font, fill="#53636c")
        y += 47
    draw.line((84, 927, 310, 927), fill="#0b6170", width=3)
    draw.text((84, 949), "РЕАЛЬНОЕ ПРИЛОЖЕНИЕ  ·  ДЕМО-ДАННЫЕ", font=ImageFont.truetype(FONT, 20), fill="#67747d")
    draw.text((84, 1002), "Интерфейс v0.3  ·  правила v0.2", font=ImageFont.truetype(FONT, 20), fill="#67747d")

    shot = Image.open(FRAMES / f"{scene.source}.png").convert("RGB")
    if scene.crop:
        shot = shot.crop(scene.crop)
    max_w, max_h = (780, 860) if scene.kind == "phone" else (1200, 820)
    shot.thumbnail((max_w, max_h), Image.Resampling.LANCZOS)
    px = 1920 - 84 - shot.width
    py = 145 + (850 - shot.height) // 2
    draw.rounded_rectangle((px - 10, py - 2, px + shot.width + 10, py + shot.height + 22), radius=22, fill="#dce5e7")
    canvas.paste(shot, (px, py))
    draw.rounded_rectangle((px - 1, py - 1, px + shot.width, py + shot.height), radius=4, outline="#cbd7d9", width=2)
    target = SLIDES / f"{scene.name}.png"
    canvas.save(target, optimize=True)
    return target


def encode(name: str, sequence: list[tuple[str, int]]) -> None:
    manifest = SLIDES / f"{name}.txt"
    with manifest.open("w") as output:
        for key, seconds in sequence:
            output.write(f"file '{render(SCENES[key])}'\n")
            output.write(f"duration {seconds}\n")
        output.write(f"file '{SLIDES / (sequence[-1][0] + '.png')}'\n")
        output.write("duration 0.033333\n")
    subprocess.run(
        [
            "ffmpeg", "-y", "-hide_banner", "-loglevel", "error", "-safe", "0", "-f", "concat", "-i", str(manifest),
            "-vf", "fps=30,format=yuv420p", "-c:v", "libx264", "-preset", "medium", "-crf", "17",
            "-movflags", "+faststart", "-an", "-t", str(sum(seconds for _, seconds in sequence)),
            str(ART / f"clinical-compass-v03-{name}.mp4"),
        ],
        check=True,
    )


def main() -> None:
    encode("full", [
        ("entry", 7), ("progress", 15), ("support", 9), ("medication", 13),
        ("symptom", 10), ("symptom_detail", 9), ("message", 10), ("emergency", 16),
        ("queue", 15), ("reason", 16), ("mis_select", 9), ("mis_open", 12),
    ])
    encode("short", [
        ("entry", 5), ("progress", 12), ("medication", 9), ("symptom", 8),
        ("emergency", 13), ("queue", 10), ("reason", 11), ("mis_open", 10),
    ])


if __name__ == "__main__":
    main()
