from __future__ import annotations

from dataclasses import dataclass


@dataclass
class FinancialAdvisorySnapshot:
    focus_area: str | None = None
    risk_level: str | None = None
    actions: list[str] | None = None
    caution: str | None = None


def _contains(text: str, words: list[str]) -> bool:
    value = (text or "").lower()
    return any(w.lower() in value for w in words)


def build_financial_advisory_snapshot(
    *,
    question_focus: str,
    latest_user_text: str,
    life_path_number: int | None = None,
) -> FinancialAdvisorySnapshot:
    text = f"{question_focus}\n{latest_user_text}".strip()
    if not text:
        return FinancialAdvisorySnapshot()

    focus_area = "គ្រប់គ្រងប្រាក់ប្រចាំថ្ងៃ"
    risk_level = "មធ្យម"
    actions: list[str] = []
    caution = "កុំវិនិយោគតាមអារម្មណ៍ ត្រូវមានផែនការច្បាស់។"

    if _contains(text, ["បំណុល", "debt", "loan", "ខ្ចី"]):
        focus_area = "រៀបចំបំណុល"
        risk_level = "ខ្ពស់"
        actions = [
            "កំណត់តារាងបង់បំណុលតាមអាទិភាព (ការប្រាក់ខ្ពស់មុន)",
            "កាត់ចំណាយមិនចាំបាច់ ១០-២០%",
            "កុំបន្ថែមបំណុលថ្មីបើមិនចាំបាច់",
        ]
        caution = "បំណុលត្រូវដោះជាបន្ទុកទី១ មុនចូលវិនិយោគថ្មី។"
    elif _contains(text, ["វិនិយោគ", "invest", "stock", "crypto"]):
        focus_area = "ផែនការវិនិយោគ"
        risk_level = "មធ្យមទៅខ្ពស់"
        actions = [
            "បែងចែកប្រាក់: ប្រាក់បម្រុង, ប្រាក់ប្រើប្រចាំខែ, ប្រាក់វិនិយោគ",
            "ចាប់ផ្ដើមតិចៗ និងបន្ថែមជាប្រចាំ",
            "កុំដាក់ប្រាក់ទាំងអស់ក្នុងកន្លែងតែមួយ",
        ]
        caution = "កុំសន្យាចំណេញលឿន; វិនិយោគត្រូវពិនិត្យហានិភ័យជាមុន។"
    elif _contains(text, ["រកស៊ី", "business", "អាជីវកម្ម", "លក់"]):
        focus_area = "ហិរញ្ញវត្ថុអាជីវកម្មតូច"
        risk_level = "មធ្យម"
        actions = [
            "បែងចែកគណនីផ្ទាល់ខ្លួន និងអាជីវកម្មឱ្យដាច់",
            "កត់ចំណូល-ចំណាយរៀងរាល់ថ្ងៃ",
            "ទុកប្រាក់បម្រុងអាជីវកម្មយ៉ាងតិច ២-៣ ខែ",
        ]
    elif _contains(text, ["សន្សំ", "save", "saving"]):
        focus_area = "សន្សំប្រាក់"
        risk_level = "ទាប"
        actions = [
            "កំណត់ច្បាប់សន្សំជារៀងរាល់ខែ (ឧ. 20%)",
            "ប្រើវិធី 50/30/20 សម្រាប់ចំណាយ",
            "បង្កើតប្រាក់បម្រុងបន្ទាន់ 3-6 ខែ",
        ]

    if not actions:
        actions = [
            "កត់ត្រាចំណូល-ចំណាយប្រចាំថ្ងៃ",
            "ទុកប្រាក់បម្រុងមុនចំណាយលើអ្វីធំៗ",
            "ពិនិត្យគោលដៅលុយរៀងរាល់ខែ",
        ]

    if life_path_number in {4, 8}:
        actions.append("លេខផ្លូវជីវិតបង្ហាញថាត្រូវប្រើវិន័យខ្ពស់ និងគោរពផែនការលុយឱ្យតឹង")
    elif life_path_number in {3, 5}:
        actions.append("ត្រូវប្រយ័ត្នចំណាយតាមអារម្មណ៍ និងការប្តូរផែនការញឹកញាប់")

    return FinancialAdvisorySnapshot(
        focus_area=focus_area,
        risk_level=risk_level,
        actions=actions,
        caution=caution,
    )

