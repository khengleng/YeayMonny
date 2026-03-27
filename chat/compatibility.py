from __future__ import annotations

import re
from dataclasses import dataclass

from .astrology import AstrologySnapshot, build_astrology_snapshot
from .fengshui import EARTHLY_BRANCHES_KM

RELATION_STAGE_KEYWORDS = {
    "រៀបការ": "Married",
    "ភ្ជាប់ពាក្យ": "Engaged",
    "ស្នេហា": "Dating",
    "dating": "Dating",
    "married": "Married",
    "engaged": "Engaged",
    "separated": "Separated",
    "divorced": "Divorced",
    "បែកគ្នា": "Breakup",
    "crush": "Crush",
}

INTENT_KEYWORDS = {
    "ត្រូវគ្នា": "Check compatibility",
    "reconnect": "Reconnect",
    "ត្រលប់មកវិញ": "Reconnect",
    "move on": "Move forward",
    "បន្តទៅមុខ": "Move forward",
    "feel": "Understand feelings",
    "អារម្មណ៍": "Understand feelings",
}

WESTERN_SIGN_GROUP = {
    "មករ": "Earth",
    "គោ": "Earth",
    "កុម្ភៈ": "Air",
    "មីន": "Water",
    "មេស": "Fire",
    "ឧសភា": "Earth",
    "មិថុនា": "Air",
    "កក្កដា": "Water",
    "សីហា": "Fire",
    "កញ្ញា": "Earth",
    "តុលា": "Air",
    "វិច្ឆិកា": "Water",
    "ធ្នូ": "Fire",
}


@dataclass
class CompatibilitySnapshot:
    partner_birth_info: str | None = None
    partner_year: int | None = None
    partner_animal: str | None = None
    partner_western_sign: str | None = None
    relation_stage: str | None = None
    intent: str | None = None
    score: int | None = None
    level: str | None = None
    key_notes: list[str] | None = None
    guidance: str | None = None


def _extract_year_candidates(text: str) -> list[int]:
    found = re.findall(r"(19\d{2}|20\d{2})", text or "")
    return [int(x) for x in found]


def _extract_partner_birth_info(text: str, user_year: int | None) -> str:
    years = _extract_year_candidates(text)
    for y in years:
        if user_year and y == user_year:
            continue
        return str(y)
    return ""


def _zodiac_score(user_year: int, partner_year: int) -> tuple[int, str]:
    u = (user_year - 4) % 12
    p = (partner_year - 4) % 12
    diff = (p - u) % 12
    if diff in {4, 8}:
        return 34, "ឆ្នាំចិនសមគ្នា (ចន្លោះ៤ឆ្នាំ)"
    if diff == 6:
        return 12, "ឆ្នាំចិនប្រភេទប៉ះគ្នា (ឆ្លង៦ឆ្នាំ)"
    if diff in {3, 9}:
        return 18, "ឆ្នាំចិនងាយខ្វែងគំនិត (ឆ្លង៣ឆ្នាំ)"
    return 24, "ឆ្នាំចិនមធ្យម ត្រូវសម្របសម្រួលគ្នា"


def _life_path_score(a: int | None, b: int | None) -> tuple[int, str]:
    if not a or not b:
        return 20, "មិនទាន់មានលេខផ្លូវជីវិតគ្រប់គ្រាន់"
    diff = abs(a - b)
    if diff in {0, 1, 2}:
        return 30, "លេខផ្លូវជីវិតទៅទិសដៅស្រដៀងគ្នា"
    if diff in {3, 4}:
        return 22, "លេខផ្លូវជីវិតខុសគ្នាបន្តិច ត្រូវគាំទ្រគ្នា"
    return 16, "លេខផ្លូវជីវិតខុសច្រើន ត្រូវនិយាយច្បាស់អំពីគោលដៅ"


def _western_score(a: str | None, b: str | None) -> tuple[int, str]:
    if not a or not b:
        return 18, "មិនទាន់មានសញ្ញាផ្កាយពេញលេញ"
    ga = WESTERN_SIGN_GROUP.get(a)
    gb = WESTERN_SIGN_GROUP.get(b)
    if not ga or not gb:
        return 18, "សញ្ញាផ្កាយមិនទាន់គ្រប់គ្រាន់"
    if ga == gb:
        return 26, "សញ្ញាផ្កាយធាតុស្រដៀងគ្នា"
    pair = {ga, gb}
    if pair in ({"Fire", "Air"}, {"Water", "Earth"}):
        return 24, "ធាតុផ្កាយគាំទ្រគ្នា"
    return 16, "ធាតុផ្កាយខុសចំណុច ត្រូវអត់ធ្មត់ពេលខ្លះ"


def _score_level(score: int) -> str:
    if score >= 78:
        return "ខ្លាំង"
    if score >= 58:
        return "ល្អមធ្យម"
    return "ត្រូវប្រឹងសម្របសម្រួល"


def _detect_stage(text: str) -> str | None:
    lower = (text or "").lower()
    for key, label in RELATION_STAGE_KEYWORDS.items():
        if key.lower() in lower:
            return label
    return None


def _detect_intent(text: str) -> str | None:
    lower = (text or "").lower()
    for key, label in INTENT_KEYWORDS.items():
        if key.lower() in lower:
            return label
    return None


def build_compatibility_snapshot(
    *,
    user_birth_info: str,
    question_focus: str,
    latest_user_text: str,
) -> CompatibilitySnapshot:
    combined = f"{question_focus}\n{latest_user_text}".strip()
    user_ast = build_astrology_snapshot(user_birth_info)
    partner_birth_info = _extract_partner_birth_info(combined, user_ast.year)
    if not partner_birth_info:
        return CompatibilitySnapshot(
            relation_stage=_detect_stage(combined),
            intent=_detect_intent(combined),
        )

    partner_ast = build_astrology_snapshot(partner_birth_info)
    if not user_ast.year or not partner_ast.year:
        return CompatibilitySnapshot(
            partner_birth_info=partner_birth_info,
            relation_stage=_detect_stage(combined),
            intent=_detect_intent(combined),
        )

    s1, note1 = _zodiac_score(user_ast.year, partner_ast.year)
    s2, note2 = _life_path_score(user_ast.life_path_number, partner_ast.life_path_number)
    s3, note3 = _western_score(user_ast.western_sign, partner_ast.western_sign)
    score = max(0, min(100, s1 + s2 + s3))
    level = _score_level(score)

    if score >= 78:
        guidance = "ទំនាក់ទំនងមានមូលដ្ឋានល្អ ចៅគួររក្សាការនិយាយត្រង់ៗ និងគោរពពេលវេលាគ្នាទៅវិញទៅមក។"
    elif score >= 58:
        guidance = "មានចំណុចល្អ និងចំណុចត្រូវកែ។ ចៅគួរច្បាស់លើការរំពឹងទុក និងដោះស្រាយរឿងតូចៗកុំឱ្យកក។"
    else:
        guidance = "មិនមែនថាមិនបានទេ ប៉ុន្តែត្រូវការការខិតខំខ្លាំងលើការយល់ចិត្ត និងការគ្រប់គ្រងអារម្មណ៍។"

    return CompatibilitySnapshot(
        partner_birth_info=partner_birth_info,
        partner_year=partner_ast.year,
        partner_animal=EARTHLY_BRANCHES_KM[(partner_ast.year - 4) % 12],
        partner_western_sign=partner_ast.western_sign,
        relation_stage=_detect_stage(combined),
        intent=_detect_intent(combined),
        score=score,
        level=level,
        key_notes=[note1, note2, note3],
        guidance=guidance,
    )

