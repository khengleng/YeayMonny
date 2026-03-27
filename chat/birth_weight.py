from __future__ import annotations

import re
from dataclasses import dataclass

from .astrology import KHMER_DIGITS_MAP, extract_birth_parts

# Simplified birth-weight style calculator inspired by classical "weight at birth"
# methods used in Chinese metaphysics tools. This is an approximate engine.
YEAR_WEIGHT = {
    0: 1.2,   # Rat
    1: 0.9,   # Ox
    2: 1.0,   # Tiger
    3: 0.8,   # Rabbit
    4: 1.2,   # Dragon
    5: 1.0,   # Snake
    6: 1.1,   # Horse
    7: 0.7,   # Goat
    8: 1.0,   # Monkey
    9: 0.8,   # Rooster
    10: 0.9,  # Dog
    11: 0.7,  # Pig
}

MONTH_WEIGHT = {
    1: 0.6, 2: 0.7, 3: 1.0, 4: 0.9, 5: 0.5, 6: 1.6,
    7: 0.9, 8: 1.5, 9: 1.8, 10: 0.8, 11: 0.9, 12: 0.5,
}

DAY_WEIGHT = {d: ((d % 9) + 1) / 10 for d in range(1, 32)}
HOUR_WEIGHT = {h: (((h // 2) % 6) + 4) / 10 for h in range(24)}


@dataclass
class BirthWeightSnapshot:
    year: int | None = None
    month: int | None = None
    day: int | None = None
    hour: int | None = None
    total_weight: float | None = None
    result_label: str | None = None
    note: str | None = None


def _extract_hour(text: str) -> int | None:
    normalized = (text or "").translate(KHMER_DIGITS_MAP)
    match = re.search(r"(\d{1,2})[:hH](\d{1,2})", normalized)
    if match:
        hh = int(match.group(1))
        if 0 <= hh <= 23:
            return hh
    # fallback standalone hour hint, e.g. "កើតម៉ោង 14"
    m2 = re.search(r"(?:ម៉ោង|hour)\s*(\d{1,2})", normalized, flags=re.IGNORECASE)
    if m2:
        hh = int(m2.group(1))
        if 0 <= hh <= 23:
            return hh
    return None


def _label(total: float) -> tuple[str, str]:
    if total >= 4.2:
        return ("ធ្ងន់ខ្លាំង", "មានថាមពលដឹកនាំល្អ តែត្រូវប្រើចិត្តស្ងប់ និងគោរពវិន័យ។")
    if total >= 3.2:
        return ("មធ្យមល្អ", "ផ្លូវជីវិតស្ថិរភាពល្អ បើចៅបន្តខិតខំជាបន្តបន្ទាប់។")
    if total >= 2.4:
        return ("មធ្យម", "ត្រូវអត់ធ្មត់ និងរៀបផែនការច្បាស់ ដើម្បីឱ្យលទ្ធផលប្រសើរ។")
    return ("ស្រាល", "គួរបន្ថែមវិន័យ និងសន្សំកម្លាំង មិនគួរប្រញាប់ជ្រុល។")


def build_birth_weight_snapshot(birth_info: str) -> BirthWeightSnapshot:
    year, month, day = extract_birth_parts(birth_info)
    if not (year and month and day):
        return BirthWeightSnapshot()

    hour = _extract_hour(birth_info)
    zodiac_idx = (year - 4) % 12
    total = YEAR_WEIGHT[zodiac_idx] + MONTH_WEIGHT.get(month, 0.8) + DAY_WEIGHT.get(day, 0.5)
    if hour is not None:
        total += HOUR_WEIGHT.get(hour, 0.6)
    label, note = _label(round(total, 2))
    return BirthWeightSnapshot(
        year=year,
        month=month,
        day=day,
        hour=hour,
        total_weight=round(total, 2),
        result_label=label,
        note=note,
    )

