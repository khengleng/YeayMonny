from __future__ import annotations

from dataclasses import dataclass

from .astrology import extract_birth_parts

HEAVENLY_STEMS_KM = [
    "ជា",
    "អ៊ី",
    "ប៊ីង",
    "ឌីង",
    "អ៊ូ",
    "ជី",
    "កេង",
    "ស៊ីន",
    "រ៉ែន",
    "គួយ",
]

EARTHLY_BRANCHES_KM = [
    "កណ្ដុរ",
    "គោ",
    "ខ្លា",
    "ទន្សាយ",
    "នាគ",
    "ពស់",
    "សេះ",
    "ចៀម",
    "ស្វា",
    "មាន់",
    "ឆ្កែ",
    "ជ្រូក",
]

STEM_ELEMENT = {
    0: "ឈើ",
    1: "ឈើ",
    2: "ភ្លើង",
    3: "ភ្លើង",
    4: "ដី",
    5: "ដី",
    6: "លោហៈ",
    7: "លោហៈ",
    8: "ទឹក",
    9: "ទឹក",
}

ELEMENT_COLORS = {
    "ឈើ": ["បៃតង", "ខៀវស្រាល"],
    "ភ្លើង": ["ក្រហម", "ស្វាយក្រហម", "ផ្កាឈូក"],
    "ដី": ["លឿង", "ត្នោត"],
    "លោហៈ": ["ស", "ប្រផេះ", "មាស"],
    "ទឹក": ["ខៀវ", "ខ្មៅ"],
}

KUA_DIRECTIONS = {
    1: ["ជើង", "កើត", "អាគ្នេយ៍", "ត្បូង"],
    2: ["ឦសាន", "ពាយ័ព្យ", "លិច", "និរតី"],
    3: ["ត្បូង", "ជើង", "អាគ្នេយ៍", "កើត"],
    4: ["ជើង", "ត្បូង", "កើត", "អាគ្នេយ៍"],
    6: ["ពាយ័ព្យ", "លិច", "ឦសាន", "និរតី"],
    7: ["លិច", "ពាយ័ព្យ", "និរតី", "ឦសាន"],
    8: ["និរតី", "ឦសាន", "លិច", "ពាយ័ព្យ"],
    9: ["កើត", "អាគ្នេយ៍", "ជើង", "ត្បូង"],
}


@dataclass
class FengShuiSnapshot:
    year: int | None = None
    stem_name: str | None = None
    branch_name: str | None = None
    element: str | None = None
    kua_male: int | None = None
    kua_female: int | None = None
    favorable_directions_male: list[str] | None = None
    favorable_directions_female: list[str] | None = None
    lucky_colors: list[str] | None = None


def _reduce_to_digit(n: int) -> int:
    value = n
    while value > 9:
        value = sum(int(d) for d in str(value))
    return value


def _kua_number(year: int, *, is_male: bool) -> int:
    yy = year % 100
    reduced = _reduce_to_digit((yy // 10) + (yy % 10))
    if is_male:
        base = 9 if year >= 2000 else 10
        kua = base - reduced
        if kua <= 0:
            kua += 9
        if kua == 5:
            return 2
        return kua

    base = 6 if year >= 2000 else 5
    kua = _reduce_to_digit(reduced + base)
    if kua == 5:
        return 8
    return kua


def build_fengshui_snapshot(birth_info: str) -> FengShuiSnapshot:
    year, _month, _day = extract_birth_parts(birth_info)
    if not year:
        return FengShuiSnapshot()

    stem_index = (year - 4) % 10
    branch_index = (year - 4) % 12
    element = STEM_ELEMENT[stem_index]
    kua_male = _kua_number(year, is_male=True)
    kua_female = _kua_number(year, is_male=False)

    return FengShuiSnapshot(
        year=year,
        stem_name=HEAVENLY_STEMS_KM[stem_index],
        branch_name=EARTHLY_BRANCHES_KM[branch_index],
        element=element,
        kua_male=kua_male,
        kua_female=kua_female,
        favorable_directions_male=KUA_DIRECTIONS.get(kua_male, []),
        favorable_directions_female=KUA_DIRECTIONS.get(kua_female, []),
        lucky_colors=ELEMENT_COLORS.get(element, []),
    )
