"""Inspect encoded videos and make contact sheets from decoded MP4 frames."""

from __future__ import annotations

import json
import subprocess
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont


ROOT = Path(__file__).resolve().parents[2]
ART = ROOT / "artifacts/demo"
FONT = ImageFont.truetype("/usr/share/fonts/TTF/FiraSans-Regular.ttf", 20)
PLANS = {
    "full": [7, 15, 9, 13, 10, 9, 10, 16, 15, 16, 9, 12],
    "short": [5, 12, 9, 8, 13, 10, 11, 10],
}


def probe(video: Path) -> dict:
    result = subprocess.check_output(
        ["ffprobe", "-v", "error", "-show_entries", "format=duration,size:stream=codec_name,width,height,r_frame_rate", "-of", "json", str(video)],
        text=True,
    )
    return json.loads(result)


def frame(video: Path, second: float, target: Path) -> None:
    subprocess.run(
        ["ffmpeg", "-y", "-hide_banner", "-loglevel", "error", "-ss", str(second), "-i", str(video), "-frames:v", "1", str(target)],
        check=True,
    )


def main() -> None:
    lines = ["# Проверка видео", "", "Кадры контактных листов декодированы из итоговых MP4.", ""]
    for name, durations in PLANS.items():
        video = ART / f"clinical-compass-v03-{name}.mp4"
        data = probe(video)
        stream = data["streams"][0]
        duration = float(data["format"]["duration"])
        expected = sum(durations)
        assert stream["width"] == 1920 and stream["height"] == 1080, stream
        assert stream["r_frame_rate"] == "30/1", stream
        assert abs(duration - expected) < 0.2, (duration, expected)
        if name == "full":
            assert 120 <= duration <= 150
        else:
            assert 60 <= duration <= 90
        columns = 4
        rows = (len(durations) + columns - 1) // columns
        sheet = Image.new("RGB", (columns * 480, rows * 300), "#e8eef0")
        draw = ImageDraw.Draw(sheet)
        elapsed = 0
        for index, segment in enumerate(durations):
            second = elapsed + segment / 2
            temp = ART / f".qa-{name}-{index:02d}.png"
            frame(video, second, temp)
            im = Image.open(temp).convert("RGB").resize((480, 270), Image.Resampling.LANCZOS)
            x, y = (index % columns) * 480, (index // columns) * 300
            sheet.paste(im, (x, y))
            draw.text((x + 10, y + 274), f"{index + 1:02d}  {int(second // 60):02d}:{int(second % 60):02d}", fill="#17252d", font=FONT)
            temp.unlink()
            elapsed += segment
        contact = ART / f"contact-sheet-{name}.jpg"
        sheet.save(contact, quality=90)
        lines += [
            f"## {name}", "",
            f"- Длительность: {duration:.2f} с; ожидается {expected} с.",
            f"- Видео: H.264, 1920×1080, 30 FPS, {int(data['format']['size']) / 1024 / 1024:.1f} МБ.",
            f"- Контактный лист: `{contact.name}`; {len(durations)} проверенных сцен.",
            "",
        ]
    (ART / "QA_REPORT.md").write_text("\n".join(lines), encoding="utf-8")


if __name__ == "__main__":
    main()
