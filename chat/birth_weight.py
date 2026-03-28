from __future__ import annotations

import re
from dataclasses import dataclass

from lunardate import LunarDate

from .astrology import KHMER_DIGITS_MAP, extract_birth_parts

# Tables aligned to published bone-weight chart method (liang.qian -> stored as qian).
# Source alignment target: skillon.com and equivalent Yuan Tiangang tables.
YEAR_WEIGHT_QIAN = {
    "jia-zi": 12, "yi-chou": 9, "bing-yin": 6, "ding-mao": 7, "wu-chen": 12, "ji-si": 5,
    "geng-wu": 9, "xin-wei": 8, "ren-shen": 7, "gui-you": 8, "jia-xu": 15, "yi-hai": 9,
    "bing-zi": 16, "ding-chou": 8, "wu-yin": 8, "ji-mao": 19, "geng-chen": 12, "xin-si": 6,
    "ren-wu": 8, "gui-wei": 7, "jia-shen": 5, "yi-you": 15, "bing-xu": 6, "ding-hai": 16,
    "wu-zi": 15, "ji-chou": 7, "geng-yin": 9, "xin-mao": 12, "ren-chen": 10, "gui-si": 7,
    "jia-wu": 15, "yi-wei": 6, "bing-shen": 5, "ding-you": 14, "wu-xu": 14, "ji-hai": 9,
    "geng-zi": 7, "xin-chou": 7, "ren-yin": 9, "gui-mao": 12, "jia-chen": 8, "yi-si": 7,
    "bing-wu": 13, "ding-wei": 5, "wu-shen": 14, "ji-you": 5, "geng-xu": 9, "xin-hai": 17,
    "ren-zi": 5, "gui-chou": 7, "jia-yin": 12, "yi-mao": 8, "bing-chen": 8, "ding-si": 6,
    "wu-wu": 19, "ji-wei": 6, "geng-shen": 8, "xin-you": 16, "ren-xu": 10, "gui-hai": 6,
}

MONTH_WEIGHT_QIAN = {
    1: 6, 2: 7, 3: 18, 4: 9, 5: 5, 6: 16,
    7: 9, 8: 15, 9: 18, 10: 8, 11: 9, 12: 5,
}

DAY_WEIGHT_QIAN = {
    1: 5, 2: 10, 3: 8, 4: 15, 5: 16, 6: 15, 7: 8, 8: 16, 9: 8, 10: 16,
    11: 9, 12: 17, 13: 8, 14: 17, 15: 10, 16: 8, 17: 9, 18: 8, 19: 5, 20: 10,
    21: 10, 22: 9, 23: 8, 24: 9, 25: 15, 26: 18, 27: 7, 28: 8, 29: 16, 30: 6,
}

HEAVENLY_STEMS = ["jia", "yi", "bing", "ding", "wu", "ji", "geng", "xin", "ren", "gui"]
EARTHLY_BRANCHES = ["zi", "chou", "yin", "mao", "chen", "si", "wu", "wei", "shen", "you", "xu", "hai"]


@dataclass
class BirthWeightSnapshot:
    year: int | None = None
    month: int | None = None
    day: int | None = None
    hour: int | None = None
    lunar_year: int | None = None
    lunar_month: int | None = None
    lunar_day: int | None = None
    year_weight_qian: int | None = None
    month_weight_qian: int | None = None
    day_weight_qian: int | None = None
    hour_weight_qian: int | None = None
    total_weight: float | None = None
    result_label: str | None = None
    note: str | None = None


def _extract_time(text: str) -> tuple[int | None, int]:
    normalized = (text or "").translate(KHMER_DIGITS_MAP)
    match = re.search(r"(\d{1,2})[:hH](\d{1,2})", normalized)
    if match:
        hh = int(match.group(1))
        mm = int(match.group(2))
        if 0 <= hh <= 23 and 0 <= mm <= 59:
            return hh, mm

    m2 = re.search(r"(?:ម៉ោង|hour)\s*(\d{1,2})", normalized, flags=re.IGNORECASE)
    if m2:
        hh = int(m2.group(1))
        if 0 <= hh <= 23:
            return hh, 0
    return None, 0


def _hour_weight_qian_by_wofs_slot(hour: int | None, minute: int) -> int:
    if hour is None:
        return 0
    # WOFS slots:
    # 2301-0100, 0101-0300, 0301-0500, 0501-0700, 0701-0900, 0901-1100,
    # 1101-1300, 1301-1500, 1501-1700, 1701-1900, 1901-2100, 2101-2300
    # We keep exact boundary behavior.
    if (hour == 23 and minute >= 1) or hour == 0 or (hour == 1 and minute == 0):
        return 16
    if (hour == 1 and minute >= 1) or hour == 2 or (hour == 3 and minute == 0):
        return 6
    if (hour == 3 and minute >= 1) or hour == 4 or (hour == 5 and minute == 0):
        return 7
    if (hour == 5 and minute >= 1) or hour == 6 or (hour == 7 and minute == 0):
        return 10
    if (hour == 7 and minute >= 1) or hour == 8 or (hour == 9 and minute == 0):
        return 9
    if (hour == 9 and minute >= 1) or hour == 10 or (hour == 11 and minute == 0):
        return 16
    if (hour == 11 and minute >= 1) or hour == 12 or (hour == 13 and minute == 0):
        return 10
    if (hour == 13 and minute >= 1) or hour == 14 or (hour == 15 and minute == 0):
        return 8
    if (hour == 15 and minute >= 1) or hour == 16 or (hour == 17 and minute == 0):
        return 8
    if (hour == 17 and minute >= 1) or hour == 18 or (hour == 19 and minute == 0):
        return 9
    if (hour == 19 and minute >= 1) or hour == 20 or (hour == 21 and minute == 0):
        return 6
    # 2101-2300 (includes 23:00)
    return 6


def _year_key(year: int) -> str:
    idx = (year - 4) % 60
    stem = HEAVENLY_STEMS[idx % 10]
    branch = EARTHLY_BRANCHES[idx % 12]
    return f"{stem}-{branch}"


def _to_liang_qian(total_qian: int) -> float:
    liang = total_qian // 10
    qian = total_qian % 10
    return float(f"{liang}.{qian}")


def _label(total: float) -> tuple[str, str]:
    if total >= 6.2:
        return ("ធ្ងន់ខ្លាំង", "មានថាមពលដឹកនាំល្អ តែត្រូវប្រើចិត្តស្ងប់ និងគោរពវិន័យ។")
    if total >= 5.2:
        return ("មធ្យមល្អ", "ផ្លូវជីវិតស្ថិរភាពល្អ បើចៅបន្តខិតខំជាបន្តបន្ទាប់។")
    if total >= 3.8:
        return ("មធ្យម", "ត្រូវអត់ធ្មត់ និងរៀបផែនការច្បាស់ ដើម្បីឱ្យលទ្ធផលប្រសើរ។")
    return ("ស្រាល", "គួរបន្ថែមវិន័យ និងសន្សំកម្លាំង មិនគួរប្រញាប់ជ្រុល។")


def build_birth_weight_snapshot(birth_info: str) -> BirthWeightSnapshot:
    year, month, day = extract_birth_parts(birth_info)
    if not (year and month and day):
        return BirthWeightSnapshot()

    hour, minute = _extract_time(birth_info)
    try:
        lunar = LunarDate.fromSolarDate(year, month, day)
    except ValueError:
        return BirthWeightSnapshot(year=year, month=month, day=day, hour=hour)

    y_key = _year_key(lunar.year)
    y_qian = YEAR_WEIGHT_QIAN.get(y_key)
    m_qian = MONTH_WEIGHT_QIAN.get(lunar.month)
    d_qian = DAY_WEIGHT_QIAN.get(lunar.day)
    h_qian = _hour_weight_qian_by_wofs_slot(hour, minute)

    if y_qian is None or m_qian is None or d_qian is None:
        return BirthWeightSnapshot(
            year=year,
            month=month,
            day=day,
            hour=hour,
            lunar_year=lunar.year,
            lunar_month=lunar.month,
            lunar_day=lunar.day,
        )

    total_qian = y_qian + m_qian + d_qian + h_qian
    total = _to_liang_qian(total_qian)
    label, note = _label(total)
    return BirthWeightSnapshot(
        year=year,
        month=month,
        day=day,
        hour=hour,
        lunar_year=lunar.year,
        lunar_month=lunar.month,
        lunar_day=lunar.day,
        year_weight_qian=y_qian,
        month_weight_qian=m_qian,
        day_weight_qian=d_qian,
        hour_weight_qian=h_qian if hour is not None else None,
        total_weight=total,
        result_label=label,
        note=note,
    )
