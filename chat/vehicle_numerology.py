from __future__ import annotations

import re
from dataclasses import dataclass


KHMER_DIGITS_MAP = str.maketrans("០១២៣៤៥៦៧៨៩", "0123456789")

# Pythagorean mapping often used by online vehicle numerology calculators.
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

NUMBER_MEANINGS_KM = {
    1: "លេខនេះសម្រាប់ថាមពលដឹកនាំ ចាប់ផ្ដើមថ្មី និងការសម្រេចចិត្តរហ័ស។",
    2: "លេខនេះលើកសន្តិភាព ការសហការ និងជួយឱ្យដំណើរទៅដោយទន់ភ្លន់។",
    3: "លេខនេះគាំទ្រការទាក់ទង ការលក់ និងការងារដែលត្រូវជួបមនុស្សច្រើន។",
    4: "លេខនេះលើកវិន័យ ស្ថេរភាព និងការបើកបរដោយគោរពច្បាប់។",
    5: "លេខនេះឆាប់ផ្លាស់ប្ដូរ សាកសមដំណើរច្រើន តែត្រូវប្រយ័ត្នការប្រញាប់។",
    6: "លេខនេះផ្ដល់ថាមពលថែទាំគ្រួសារ និងការធ្វើដំណើរដើម្បីការទំនួលខុសត្រូវ។",
    7: "លេខនេះសម្រាប់ការគិតជ្រៅ និងការធ្វើដំណើរដោយស្ងប់ស្ងាត់។",
    8: "លេខនេះពាក់ព័ន្ធការងារ ហិរញ្ញវត្ថុ និងវិន័យខ្ពស់ពេលបើកបរ។",
    9: "លេខនេះលើកចិត្តមេត្តា ការជួយគេ និងការបិទបញ្ចប់ការងារធំៗ។",
}

FRIENDLY_BY_LIFE_PATH = {
    1: {1, 2, 3, 9},
    2: {1, 2, 4, 6},
    3: {1, 3, 5, 6, 9},
    4: {1, 4, 6, 8},
    5: {1, 3, 5, 6},
    6: {2, 3, 4, 5, 6, 9},
    7: {2, 7, 9},
    8: {1, 4, 6, 8},
    9: {1, 2, 3, 6, 7, 9},
}


@dataclass
class VehicleNumerologySnapshot:
    plate_raw: str | None = None
    normalized_plate: str | None = None
    total_value: int | None = None
    root_number: int | None = None
    meaning: str | None = None
    compatibility_hint: str | None = None


def _reduce_to_root(n: int) -> int:
    value = n
    while value > 9:
        value = sum(int(d) for d in str(value))
    return value


def extract_plate_candidate(text: str) -> str | None:
    normalized = (text or "").translate(KHMER_DIGITS_MAP)
    candidates = re.findall(r"[A-Za-z0-9-]{4,16}", normalized)
    if not candidates:
        return None
    # Prefer tokens that include at least 3 digits (typical plate pattern signal)
    scored = sorted(
        candidates,
        key=lambda token: (sum(c.isdigit() for c in token), len(token)),
        reverse=True,
    )
    return scored[0].upper()


def _token_value(token: str) -> int:
    total = 0
    for char in token:
        if char.isdigit():
            total += int(char)
        elif char.isalpha():
            total += LETTER_VALUES.get(char.upper(), 0)
    return total


def build_vehicle_numerology_snapshot(
    text: str,
    *,
    life_path_number: int | None = None,
) -> VehicleNumerologySnapshot:
    plate = extract_plate_candidate(text)
    if not plate:
        return VehicleNumerologySnapshot()

    total = _token_value(plate)
    if total <= 0:
        return VehicleNumerologySnapshot(plate_raw=plate, normalized_plate=plate)

    root = _reduce_to_root(total)
    meaning = NUMBER_MEANINGS_KM.get(root)
    compatibility_hint = None
    if life_path_number and 1 <= life_path_number <= 9:
        friendly_set = FRIENDLY_BY_LIFE_PATH.get(life_path_number, set())
        if root in friendly_set:
            compatibility_hint = "សមល្អជាមួយលេខផ្លូវជីវិតរបស់ចៅ"
        else:
            compatibility_hint = "មធ្យម ត្រូវបើកបរយឺតៗ និងរក្សាវិន័យឱ្យបានខ្ជាប់"

    return VehicleNumerologySnapshot(
        plate_raw=plate,
        normalized_plate=plate,
        total_value=total,
        root_number=root,
        meaning=meaning,
        compatibility_hint=compatibility_hint,
    )

