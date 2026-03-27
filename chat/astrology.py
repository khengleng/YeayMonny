from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import date

from django.utils import timezone


KHMER_DIGITS_MAP = str.maketrans("០១២៣៤៥៦៧៨៩", "0123456789")

CHINESE_ZODIAC_ANIMALS = [
    "ស្វា",
    "មាន់",
    "ឆ្កែ",
    "ជ្រូក",
    "កណ្ដុរ",
    "គោ",
    "ខ្លា",
    "ទន្សាយ",
    "នាគ",
    "ពស់",
    "សេះ",
    "ចៀម",
]

WESTERN_ZODIAC_RANGES = [
    ((1, 20), "មករ"),
    ((2, 19), "កុម្ភៈ"),
    ((3, 21), "មីន"),
    ((4, 20), "មេស"),
    ((5, 21), "ឧសភា"),
    ((6, 21), "មិថុនា"),
    ((7, 23), "កក្កដា"),
    ((8, 23), "សីហា"),
    ((9, 23), "កញ្ញា"),
    ((10, 23), "តុលា"),
    ((11, 22), "វិច្ឆិកា"),
    ((12, 22), "ធ្នូ"),
]


@dataclass
class AstrologySnapshot:
    year: int | None = None
    month: int | None = None
    day: int | None = None
    chinese_animal: str | None = None
    western_sign: str | None = None
    life_path_number: int | None = None
    age_years: int | None = None


def _to_ascii_digits(raw: str) -> str:
    return (raw or "").translate(KHMER_DIGITS_MAP)


def extract_birth_parts(birth_info: str) -> tuple[int | None, int | None, int | None]:
    text = _to_ascii_digits(birth_info)

    # Try full date first: DD-MM-YYYY or YYYY-MM-DD
    parts = re.findall(r"\d+", text)
    if len(parts) >= 3:
        a, b, c = parts[0], parts[1], parts[2]
        if len(a) == 4:
            year, month, day = int(a), int(b), int(c)
        elif len(c) == 4:
            day, month, year = int(a), int(b), int(c)
        else:
            year = month = day = None

        if year and 1 <= month <= 12 and 1 <= day <= 31:
            return year, month, day

    # Fallback year only
    years = re.findall(r"(19\d{2}|20\d{2})", text)
    if years:
        return int(years[0]), None, None
    return None, None, None


def _western_sign(month: int, day: int) -> str | None:
    try:
        # quick validity check
        date(2001, month, day)
    except ValueError:
        return None

    for (m, d), sign in WESTERN_ZODIAC_RANGES:
        if month < m or (month == m and day < d):
            return sign
    return "មករ"


def _life_path(year: int, month: int | None, day: int | None) -> int | None:
    digits = list(str(year))
    if month is not None:
        digits += list(f"{month:02d}")
    if day is not None:
        digits += list(f"{day:02d}")

    if not digits:
        return None

    total = sum(int(d) for d in digits)
    while total > 9 and total not in {11, 22, 33}:
        total = sum(int(d) for d in str(total))
    return total


def _calculate_age_years(*, year: int, month: int | None, day: int | None, reference_date: date) -> int | None:
    if month is None or day is None:
        return None

    try:
        birth_date = date(year, month, day)
    except ValueError:
        return None

    age = reference_date.year - birth_date.year
    if (reference_date.month, reference_date.day) < (birth_date.month, birth_date.day):
        age -= 1
    return max(age, 0)


def build_astrology_snapshot(birth_info: str, reference_date: date | None = None) -> AstrologySnapshot:
    year, month, day = extract_birth_parts(birth_info)
    if not year:
        return AstrologySnapshot()

    current_date = reference_date or timezone.localdate()
    animal = CHINESE_ZODIAC_ANIMALS[year % 12]
    sign = _western_sign(month, day) if month and day else None
    life_path = _life_path(year, month, day)
    age_years = _calculate_age_years(year=year, month=month, day=day, reference_date=current_date)
    return AstrologySnapshot(
        year=year,
        month=month,
        day=day,
        chinese_animal=animal,
        western_sign=sign,
        life_path_number=life_path,
        age_years=age_years,
    )
