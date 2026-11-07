"""Render docs/assets/demo.gif from the real output of `exostab check`.

The command is run for real, exactly as it is typed in the recording (with --offline, the bundled snapshot,
so the result does not depend on the network); its colored terminal output is captured and drawn frame by
frame with Pillow: the command is typed, then the report card appears. Nothing in the image is edited by hand.

    python scripts/make_demo_gif.py
"""

from __future__ import annotations

import os
import re
import shlex
import subprocess
import sys
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont
from rich.text import Text

from exostab.cli import integrating_text

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "docs" / "assets" / "demo.gif"
COMMAND = 'exostab check "TRAPPIST-1" --offline'  # typed in the recording, and run as typed
COLS = 96
FONT_SIZE = 15
FONTS = ("/System/Library/Fonts/Menlo.ttc", "/usr/share/fonts/truetype/dejavu/DejaVuSansMono.ttf")
# Rich's spinner is made of Braille patterns, which Menlo does not have: they are drawn with one of these instead.
BRAILLE_FONTS = (
    "/System/Library/Fonts/Apple Braille.ttf",
    "/usr/share/fonts/truetype/dejavu/DejaVuSansMono.ttf",
)
BRAILLE = re.compile("([\u2800-\u28ff]+)")
BG, FG = (24, 24, 27), (228, 228, 231)
DIM = (140, 140, 150)
ANSI = {  # standard ANSI colour numbers -> RGB
    1: (248, 113, 113),
    2: (74, 222, 128),
    3: (250, 204, 21),
    4: (96, 165, 250),
    5: (232, 121, 249),
    6: (103, 232, 249),
    8: DIM,
    9: (248, 113, 113),
    10: (74, 222, 128),
    11: (250, 204, 21),
    12: (96, 165, 250),
    13: (232, 121, 249),
    14: (103, 232, 249),
}


def capture() -> Text:
    env = dict(os.environ, COLUMNS=str(COLS), FORCE_COLOR="1", TERM="xterm-256color")
    env.pop("EXOSTAB_OFFLINE", None)  # the snapshot comes from --offline in COMMAND, as for a reader
    out = subprocess.run(
        [sys.executable, "-m", "exostab.cli", *shlex.split(COMMAND)[1:]],
        capture_output=True,
        text=True,
        env=env,
        check=True,
        cwd=ROOT,
    ).stdout
    # FORCE_COLOR makes Rich treat the pipe as a terminal, so the progress spinner leaves one line per
    # animation frame; keep only the report itself.
    kept = [ln for ln in out.splitlines() if "Integrating" not in ln]
    return Text.from_ansi("\n".join(kept))


def font(paths: tuple[str, ...] = FONTS) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    for path in paths:
        if Path(path).exists():
            return ImageFont.truetype(path, FONT_SIZE)
    return ImageFont.load_default()


def colour(style: object) -> tuple[int, int, int]:
    c = getattr(style, "color", None)
    if c is not None and c.triplet is not None:
        return tuple(c.triplet)  # type: ignore[return-value]
    if c is not None and c.number is not None:
        return ANSI.get(c.number, FG)
    return DIM if getattr(style, "dim", False) else FG


def main() -> None:
    text = capture()
    lines = list(text.split("\n"))
    while lines and not lines[-1].plain.strip():
        lines.pop()
    f, braille = font(), font(BRAILLE_FONTS)
    cw = f.getbbox("M")[2]
    lh = int(FONT_SIZE * 1.35)
    width = cw * (COLS + 2)
    height = lh * (len(lines) + 3)

    def frame(shown: list[Text], typed: str) -> Image.Image:
        img = Image.new("RGB", (width, height), BG)
        d = ImageDraw.Draw(img)
        d.text((cw, lh // 2), "$ ", font=f, fill=ANSI[2])
        d.text((cw * 3, lh // 2), typed, font=f, fill=FG)
        for i, ln in enumerate(shown):
            y = lh // 2 + lh * (i + 1)
            x = cw
            for span_text, style in _segments(ln):
                for part in BRAILLE.split(span_text):
                    d.text((x, y), part, font=braille if BRAILLE.fullmatch(part) else f, fill=colour(style))
                    x += cw * len(part)
        return img

    frames, durations = [], []
    for k in range(0, len(COMMAND) + 1, 2):
        frames.append(frame([], COMMAND[:k] + "▌"))
        durations.append(60)
    frames.append(frame([], COMMAND))
    durations.append(400)
    # the progress line shown while the integrations run, with the defaults of COMMAND (the real spinner is animated)
    progress = Text.assemble(("⠋", "green"), " ", integrating_text("TRAPPIST-1", 20, 1e4))
    frames.append(frame([progress], COMMAND))
    durations.append(1500)
    for n in range(1, len(lines) + 1, 3):
        frames.append(frame(lines[:n], COMMAND))
        durations.append(70)
    frames.append(frame(lines, COMMAND))
    durations.append(6000)
    OUT.parent.mkdir(parents=True, exist_ok=True)
    pal = [fr.convert("P", palette=Image.Palette.ADAPTIVE, colors=128) for fr in frames]
    pal[0].save(OUT, save_all=True, append_images=pal[1:], duration=durations, optimize=True)
    print(f"wrote {OUT} ({OUT.stat().st_size / 1e6:.2f} MB, {len(frames)} frames)")


def _segments(line: Text) -> list[tuple[str, object]]:
    from rich.console import Console

    segs = list(line.render(Console(width=10_000, color_system="truecolor")))
    return [(s.text, s.style) for s in segs if s.text]


if __name__ == "__main__":
    main()
