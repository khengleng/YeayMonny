from __future__ import annotations

import hashlib
from dataclasses import dataclass
from datetime import date

from django.utils import timezone

from .astrology import extract_birth_parts
from .fengshui import FengShuiSnapshot

DEFAULT_COLORS = ["ខៀវ", "បៃតង", "ស", "លឿង", "ក្រហម", "ត្នោត", "ប្រផេះ", "ផ្កាឈូក"]
DEFAULT_DIRECTIONS = ["កើត", "លិច", "ជើង", "ត្បូង", "អាគ្នេយ៍", "ពាយ័ព្យ", "និរតី", "ឦសាន"]
WEEKDAYS_KM = ["ចន្ទ", "អង្គារ", "ពុធ", "ព្រហស្បតិ៍", "សុក្រ", "សៅរ៍", "អាទិត្យ"]


@dataclass
class LuckySignsSnapshot:
    lucky_numbers: list[int]
    lucky_colors: list[str]
    lucky_directions: list[str]
    lucky_days: list[str]


def _seed_int(seed_text: str) -> int:
    raw = hashlib.sha256(seed_text.encode("utf-8")).hexdigest()
    return int(raw[:12], 16)


def _pick_unique(items: list[str], count: int, seed: int) -> list[str]:
    if not items:
        return []
    uniq = list(dict.fromkeys(items))
    if len(uniq) <= count:
        return uniq
    ranked = sorted(
        uniq,
        key=lambda item: hashlib.sha256(f"{seed}:{item}".encode("utf-8")).hexdigest(),
    )
    return ranked[:count]


def build_lucky_signs_snapshot(
    *,
    birth_info: str,
    question_focus: str,
    latest_user_text: str,
    feng: FengShuiSnapshot | None,
    reference_date: date | None = None,
) -> LuckySignsSnapshot:
    today = reference_date or timezone.localdate()
    year, month, day = extract_birth_parts(birth_info)
    seed_text = f"{year}-{month}-{day}|{question_focus}|{latest_user_text}|{today.isoformat()}"
    seed = _seed_int(seed_text)

    # 3 rotating lucky numbers in 1..9 (not fixed).
    start = (seed % 9) + 1
    step = ((seed // 11) % 7) + 1
    numbers: list[int] = []
    value = start
    while len(numbers) < 3:
        if value not in numbers:
            numbers.append(value)
        value = ((value + step - 1) % 9) + 1

    color_pool = list(DEFAULT_COLORS)
    if feng and feng.lucky_colors:
        color_pool = list(feng.lucky_colors) + color_pool
    lucky_colors = _pick_unique(color_pool, 3, seed // 3)

    direction_pool = list(DEFAULT_DIRECTIONS)
    if feng:
        merged = []
        if feng.favorable_directions_male:
            merged.extend(feng.favorable_directions_male)
        if feng.favorable_directions_female:
            merged.extend(feng.favorable_directions_female)
        if feng.annual_good_sectors:
            merged.extend(feng.annual_good_sectors)
        if merged:
            direction_pool = merged + direction_pool
    lucky_directions = _pick_unique(direction_pool, 2, seed // 7)

    weekday_seed = (today.weekday() + (seed % 7)) % 7
    lucky_days = [
        WEEKDAYS_KM[weekday_seed],
        WEEKDAYS_KM[(weekday_seed + 2) % 7],
    ]

    return LuckySignsSnapshot(
        lucky_numbers=numbers,
        lucky_colors=lucky_colors,
        lucky_directions=lucky_directions,
        lucky_days=lucky_days,
    )
