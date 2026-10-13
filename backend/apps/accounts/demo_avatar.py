"""
Synthetic profile pictures for DEMO employees.

DEMO / TEST DATA ONLY. Draws a small, flat-illustration head-and-shoulders
avatar (no real person, no stock photo) from a seed, so every seeded employee
gets a distinct, stable picture. Same seed always gives the same image.
"""
from __future__ import annotations

import io
import random

from PIL import Image, ImageDraw

SIZE = 256
SCALE = 4  # draw large, then downsample for smooth edges

SKIN_TONES   = ['#f1c9a5', '#e0ac82', '#c68642', '#a8693a', '#8d5524', '#f7d6bd']
HAIR_COLOURS = ['#1b1b1f', '#2c1b10', '#4a2c17', '#6b4423', '#8a8a8f', '#b5651d']
SHIRT_COLOURS = ['#5b3fd1', '#2563eb', '#0f766e', '#be185d', '#b45309', '#334155', '#7c3aed']
BACKGROUNDS = [
    ('#ede9fe', '#c4b5fd'), ('#dbeafe', '#93c5fd'), ('#dcfce7', '#86efac'),
    ('#fce7f3', '#f9a8d4'), ('#ffedd5', '#fdba74'), ('#e0e7ff', '#a5b4fc'),
]


def _gradient(top: str, bottom: str, size: int) -> Image.Image:
    base = Image.new('RGB', (size, size), top)
    draw = ImageDraw.Draw(base)
    top_rgb = tuple(int(top[i:i + 2], 16) for i in (1, 3, 5))
    bottom_rgb = tuple(int(bottom[i:i + 2], 16) for i in (1, 3, 5))
    for row in range(size):
        blend = row / (size - 1)
        colour = tuple(round(top_rgb[i] + (bottom_rgb[i] - top_rgb[i]) * blend) for i in range(3))
        draw.line([(0, row), (size, row)], fill=colour)
    return base


def _draw_person(draw: ImageDraw.ImageDraw, size: int, rng: random.Random, is_female: bool) -> None:
    skin = rng.choice(SKIN_TONES)
    hair = rng.choice(HAIR_COLOURS)
    shirt = rng.choice(SHIRT_COLOURS)
    cx = size // 2

    if is_female:  # long hair sits behind the head and shoulders
        draw.rounded_rectangle([cx - size * 0.25, size * 0.2, cx + size * 0.25, size * 0.78],
                               radius=size * 0.12, fill=hair)
    draw.ellipse([cx - size * 0.42, size * 0.7, cx + size * 0.42, size * 1.35], fill=shirt)   # shoulders
    draw.rectangle([cx - size * 0.07, size * 0.58, cx + size * 0.07, size * 0.74], fill=skin)  # neck
    draw.ellipse([cx - size * 0.19, size * 0.24, cx + size * 0.19, size * 0.64], fill=skin)    # head

    # hair on top of the head
    draw.pieslice([cx - size * 0.21, size * 0.19, cx + size * 0.21, size * 0.5], 180, 360, fill=hair)
    # face
    eye_y = size * 0.43
    for offset in (-0.075, 0.075):
        draw.ellipse([cx + size * offset - size * 0.016, eye_y - size * 0.016,
                      cx + size * offset + size * 0.016, eye_y + size * 0.016], fill='#1f2937')
    draw.arc([cx - size * 0.065, size * 0.47, cx + size * 0.065, size * 0.56], 20, 160,
             fill='#7a3b2e', width=max(2, size // 90))
    if not is_female and rng.random() < 0.3:  # stubble / beard
        draw.pieslice([cx - size * 0.17, size * 0.42, cx + size * 0.17, size * 0.7], 20, 160, fill=hair)
        draw.arc([cx - size * 0.065, size * 0.47, cx + size * 0.065, size * 0.56], 20, 160,
                 fill='#f5f5f5', width=max(2, size // 90))
    if rng.random() < 0.25:  # glasses
        for offset in (-0.075, 0.075):
            draw.ellipse([cx + size * offset - size * 0.045, eye_y - size * 0.04,
                          cx + size * offset + size * 0.045, eye_y + size * 0.05],
                         outline='#111827', width=max(2, size // 100))
        draw.line([(cx - size * 0.03, eye_y), (cx + size * 0.03, eye_y)], fill='#111827', width=max(2, size // 100))


def generate_avatar_png(seed: str, gender: str = '') -> bytes:
    """A PNG (bytes) avatar, stable for `seed`. `gender` is 'female'/'male'/'' (anything else is treated as male-styled)."""
    rng = random.Random(seed)
    big = SIZE * SCALE
    top, bottom = rng.choice(BACKGROUNDS)
    image = _gradient(top, bottom, big)
    _draw_person(ImageDraw.Draw(image), big, rng, is_female=(gender == 'female'))
    image = image.resize((SIZE, SIZE), Image.LANCZOS)
    buffer = io.BytesIO()
    image.save(buffer, format='PNG', optimize=True)
    return buffer.getvalue()
