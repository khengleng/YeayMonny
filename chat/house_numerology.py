from __future__ import annotations

import re
from dataclasses import dataclass


KHMER_DIGITS_MAP = str.maketrans("០១២៣៤៥៦៧៨៩", "0123456789")

LETTER_VALUES = {
    "A": 1,
    "B": 2,
    "C": 3,
    "D": 4,
    "E": 5,
    "F": 6,
    "G": 7,
    "H": 8,
    "I": 9,
    "J": 1,
    "K": 2,
    "L": 3,
    "M": 4,
    "N": 5,
    "O": 6,
    "P": 7,
    "Q": 8,
    "R": 9,
    "S": 1,
    "T": 2,
    "U": 3,
    "V": 4,
    "W": 5,
    "X": 6,
    "Y": 7,
    "Z": 8,
}

HOUSE_NUMBER_MEANINGS_KM = {
    1: "ផ្ទះនេះលើកថាមពលឯករាជ្យ ការដឹកនាំ និងការចាប់ផ្ដើមថ្មី។",
    2: "ផ្ទះនេះលើកសន្តិភាព ការសហការ និងទំនាក់ទំនងល្អក្នុងគ្រួសារ។",
    3: "ផ្ទះនេះលើកការទាក់ទង ភាពច្នៃប្រឌិត និងសកម្មភាពសង្គម។",
    4: "ផ្ទះនេះលើកវិន័យនិងគ្រឹះ ប៉ុន្តែអាចមានអារម្មណ៍ថាយឺត ឬតឹងតែង។",
    5: "ផ្ទះនេះលើកការផ្លាស់ប្ដូរ ចលនា និងឱកាសថ្មីៗ។",
    6: "ផ្ទះនេះសមសម្រាប់សេចក្ដីស្រឡាញ់ ការថែទាំ និងភាពកក់ក្តៅគ្រួសារ។",
    7: "ផ្ទះនេះលើកការគិតជ្រៅ ការស្ងប់ និងការស្វែងរកខ្លួនឯង។",
    8: "ផ្ទះនេះពាក់ព័ន្ធការងារនិងហិរញ្ញវត្ថុ ប៉ុន្តែត្រូវការខិតខំខ្ពស់។",
    9: "ផ្ទះនេះលើកមេត្តា ការបម្រើសង្គម និងអារម្មណ៍បញ្ចប់រឿងចាស់ៗ។",
}


@dataclass
class HouseNumerologySnapshot:
    raw_candidate: str | None = None
    moving_part: str | None = None
    total_value: int | None = None
    root_number: int | None = None
    meaning: str | None = None
    caution: str | None = None


def _reduce_to_root(n: int) -> int:
    value = n
    while value > 9:
        value = sum(int(d) for d in str(value))
    return value


def _string_value(token: str) -> int:
    total = 0
    for ch in token.upper():
        if ch.isdigit():
            total += int(ch)
        elif ch.isalpha():
            total += LETTER_VALUES.get(ch, 0)
    return total


def extract_house_candidate(text: str) -> str | None:
    normalized = (text or "").translate(KHMER_DIGITS_MAP)
    patterns = re.findall(r"[A-Za-z]?\d+[A-Za-z]?/\d+[A-Za-z]?|[A-Za-z]?\d+[A-Za-z]?", normalized)
    if not patterns:
        return None
    # Prefer slash format first (e.g., 14/18 from source article).
    patterns.sort(key=lambda p: ("/" in p, len(p)), reverse=True)
    return patterns[0].upper()


def _moving_part(candidate: str) -> str:
    token = candidate.upper()
    if "/" in token:
        # Use only moving number after slash, ignore constant block number.
        return token.split("/")[-1]
    if re.match(r"^[A-Z]\d+$", token):
        # e.g., A59 -> ignore constant letter prefix.
        return token[1:]
    return token


def build_house_numerology_snapshot(text: str) -> HouseNumerologySnapshot:
    candidate = extract_house_candidate(text)
    if not candidate:
        return HouseNumerologySnapshot()

    moving = _moving_part(candidate)
    total = _string_value(moving)
    if total <= 0:
        return HouseNumerologySnapshot(raw_candidate=candidate, moving_part=moving)

    root = _reduce_to_root(total)
    caution = None
    if root in {4, 8}:
        caution = "លេខនេះត្រូវការវិន័យខ្ពស់ និងការរៀបចំផ្ទះឱ្យស្អាតស្ងប់ជានិច្ច ដើម្បីបន្ថយសម្ពាធ។"

    return HouseNumerologySnapshot(
        raw_candidate=candidate,
        moving_part=moving,
        total_value=total,
        root_number=root,
        meaning=HOUSE_NUMBER_MEANINGS_KM.get(root),
        caution=caution,
    )

