from __future__ import annotations

from dataclasses import dataclass
from datetime import date

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

ANNUAL_BASE_LAYOUT = {
    "ពាយ័ព្យ": 6,
    "លិច": 7,
    "ឦសាន": 8,
    "ត្បូង": 9,
    "ជើង": 1,
    "និរតី": 2,
    "កើត": 3,
    "អាគ្នេយ៍": 4,
    "មជ្ឈមណ្ឌល": 5,
}

GOOD_STARS = {1, 6, 8, 9}
CAUTION_STARS = {2, 3, 5, 7}

ZODIAC_TRIADS = (
    (0, 4, 8),   # Rat, Dragon, Monkey
    (1, 5, 9),   # Ox, Snake, Rooster
    (2, 6, 10),  # Tiger, Horse, Dog
    (3, 7, 11),  # Rabbit, Goat, Pig
)

ANIMAL_MAIN_DIRECTIONS = {
    0: "ជើង",
    1: "ឦសាន",
    2: "ឦសាន",
    3: "កើត",
    4: "អាគ្នេយ៍",
    5: "អាគ្នេយ៍",
    6: "ត្បូង",
    7: "និរតី",
    8: "និរតី",
    9: "លិច",
    10: "ពាយ័ព្យ",
    11: "ពាយ័ព្យ",
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
    caution_directions_male: list[str] | None = None
    caution_directions_female: list[str] | None = None
    lucky_colors: list[str] | None = None
    harmony_animals: list[str] | None = None
    clash_animal: str | None = None
    annual_center_star: int | None = None
    annual_star_layout: dict[str, int] | None = None
    annual_good_sectors: list[str] | None = None
    annual_caution_sectors: list[str] | None = None
    tai_sui_direction: str | None = None
    sui_po_direction: str | None = None
    ben_ming_nian: bool = False
    four_apart_animals: list[str] | None = None
    three_apart_animals: list[str] | None = None
    partner_relation: str | None = None
    partner_animal: str | None = None


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


def _annual_center_star(year: int) -> int:
    yy = year % 100
    reduced = _reduce_to_digit((yy // 10) + (yy % 10))
    base = 9 if year >= 2000 else 10
    center = base - reduced
    while center <= 0:
        center += 9
    return center


def _shift_star(base_star: int, center_star: int) -> int:
    shifted = ((base_star + (center_star - 5) - 1) % 9) + 1
    return shifted


def _annual_layout(center_star: int) -> dict[str, int]:
    return {sector: _shift_star(star, center_star) for sector, star in ANNUAL_BASE_LAYOUT.items()}


def _sectors_for_stars(layout: dict[str, int], target: set[int]) -> list[str]:
    return [sector for sector, star in layout.items() if sector != "មជ្ឈមណ្ឌល" and star in target]


def _harmony_animals(branch_index: int) -> list[str]:
    for triad in ZODIAC_TRIADS:
        if branch_index in triad:
            peers = [EARTHLY_BRANCHES_KM[idx] for idx in triad if idx != branch_index]
            return peers
    return []


def _clash_animal(branch_index: int) -> str:
    return EARTHLY_BRANCHES_KM[(branch_index + 6) % 12]


def _yearly_tai_sui(reference_year: int) -> tuple[str, str]:
    year_branch_index = (reference_year - 4) % 12
    tai_sui_direction = ANIMAL_MAIN_DIRECTIONS[year_branch_index]
    sui_po_direction = ANIMAL_MAIN_DIRECTIONS[(year_branch_index + 6) % 12]
    return tai_sui_direction, sui_po_direction


def _relation_label(user_idx: int, partner_idx: int) -> str:
    diff = (partner_idx - user_idx) % 12
    if diff in {4, 8}:
        return "សមគ្នាល្អ (ចន្លោះ៤ឆ្នាំ)"
    if diff == 6:
        return "ប៉ះទង្គិចខ្លាំង (ឆ្លង៦ឆ្នាំ)"
    if diff in {3, 9}:
        return "ងាយខ្វែងគំនិត (ឆ្លង៣ឆ្នាំ)"
    return "មធ្យម ត្រូវសម្របសម្រួល"


def build_fengshui_snapshot(
    birth_info: str,
    *,
    reference_year: int | None = None,
    partner_birth_info: str = "",
) -> FengShuiSnapshot:
    year_for_chart = reference_year or date.today().year
    center_star = _annual_center_star(year_for_chart)
    annual_layout = _annual_layout(center_star)
    tai_sui_direction, sui_po_direction = _yearly_tai_sui(year_for_chart)
    partner_year, _pm, _pd = extract_birth_parts(partner_birth_info)
    year, _month, _day = extract_birth_parts(birth_info)
    if not year:
        return FengShuiSnapshot(
            annual_center_star=center_star,
            annual_star_layout=annual_layout,
            annual_good_sectors=_sectors_for_stars(annual_layout, GOOD_STARS),
            annual_caution_sectors=_sectors_for_stars(annual_layout, CAUTION_STARS),
            tai_sui_direction=tai_sui_direction,
            sui_po_direction=sui_po_direction,
        )

    stem_index = (year - 4) % 10
    branch_index = (year - 4) % 12
    element = STEM_ELEMENT[stem_index]
    kua_male = _kua_number(year, is_male=True)
    kua_female = _kua_number(year, is_male=False)
    all_dirs = ["ជើង", "ត្បូង", "កើត", "អាគ្នេយ៍", "លិច", "ពាយ័ព្យ", "និរតី", "ឦសាន"]
    caution_male = [d for d in all_dirs if d not in KUA_DIRECTIONS.get(kua_male, [])]
    caution_female = [d for d in all_dirs if d not in KUA_DIRECTIONS.get(kua_female, [])]
    four_apart_animals = [EARTHLY_BRANCHES_KM[(branch_index + 4) % 12], EARTHLY_BRANCHES_KM[(branch_index + 8) % 12]]
    three_apart_animals = [EARTHLY_BRANCHES_KM[(branch_index + 3) % 12], EARTHLY_BRANCHES_KM[(branch_index + 9) % 12]]
    partner_relation = None
    partner_animal = None
    if partner_year:
        partner_idx = (partner_year - 4) % 12
        partner_animal = EARTHLY_BRANCHES_KM[partner_idx]
        partner_relation = _relation_label(branch_index, partner_idx)

    return FengShuiSnapshot(
        year=year,
        stem_name=HEAVENLY_STEMS_KM[stem_index],
        branch_name=EARTHLY_BRANCHES_KM[branch_index],
        element=element,
        kua_male=kua_male,
        kua_female=kua_female,
        favorable_directions_male=KUA_DIRECTIONS.get(kua_male, []),
        favorable_directions_female=KUA_DIRECTIONS.get(kua_female, []),
        caution_directions_male=caution_male,
        caution_directions_female=caution_female,
        lucky_colors=ELEMENT_COLORS.get(element, []),
        harmony_animals=_harmony_animals(branch_index),
        clash_animal=_clash_animal(branch_index),
        annual_center_star=center_star,
        annual_star_layout=annual_layout,
        annual_good_sectors=_sectors_for_stars(annual_layout, GOOD_STARS),
        annual_caution_sectors=_sectors_for_stars(annual_layout, CAUTION_STARS),
        tai_sui_direction=tai_sui_direction,
        sui_po_direction=sui_po_direction,
        ben_ming_nian=((year_for_chart - year) % 12 == 0),
        four_apart_animals=four_apart_animals,
        three_apart_animals=three_apart_animals,
        partner_relation=partner_relation,
        partner_animal=partner_animal,
    )
