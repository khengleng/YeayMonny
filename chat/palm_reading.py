from __future__ import annotations

import re


def _has_any(text: str, patterns: list[str]) -> bool:
    return any(re.search(pattern, text, flags=re.IGNORECASE) for pattern in patterns)


def _looks_like_palm_context(text: str) -> bool:
    if _has_any(
        text,
        [
            r"not.*palm",
            r"no palm",
            r"មិនឃើញបាតដៃ",
            r"មិនមែនបាតដៃ",
        ],
    ):
        return False
    return _has_any(
        text,
        [
            r"បាតដៃ",
            r"ដៃ",
            r"palm",
            r"hand",
            r"life line",
            r"head line",
            r"heart line",
            r"fate line",
            r"sun line",
            r"បន្ទាត់ជីវិត",
            r"បន្ទាត់គំនិត",
            r"បន្ទាត់បេះដូង",
            r"បន្ទាត់វាសនា",
        ],
    )


def build_palm_reading_engine_notes(observation_text: str) -> str:
    """
    Rule-based palm reading notes inspired by Allure's beginner framework:
    heart line, head line, life line, fate line, and sun line interpretation.
    """
    text = (observation_text or "").strip()
    if not text or not _looks_like_palm_context(text):
        return ""

    notes: list[str] = ["សេចក្ដីបកស្រាយបន្ថែមតាមបន្ទាត់បាតដៃ"]

    if _has_any(text, [r"បន្ទាត់គំនិត", r"head line", r"line.*head"]):
        if _has_any(text, [r"ត្រង់", r"straight", r"ច្បាស់"]):
            notes.append("- បន្ទាត់គំនិត៖ ស្ទីលគិតជាក់ស្តែង មានរបៀប និងគិតជំហានមុនសម្រេចចិត្ត។")
        elif _has_any(text, [r"រលក", r"wavy", r"កោងច្រើន"]):
            notes.append("- បន្ទាត់គំនិត៖ គំនិតបត់បែន ច្នៃប្រឌិតខ្ពស់ តែត្រូវមានផែនការដើម្បីកុំរាយប៉ាយ។")
        if _has_any(text, [r"ខូច", r"ដាច់", r"break"]):
            notes.append("- បន្ទាត់គំនិតមានចន្លោះ៖ មានវគ្គបម្លែងគំនិតធំៗក្នុងជីវិត និងរៀនពីបទពិសោធន៍ខ្លាំង។")

    if _has_any(text, [r"បន្ទាត់បេះដូង", r"heart line", r"love line"]):
        if _has_any(text, [r"វែង", r"long", r"ជ្រៅ", r"deep"]):
            notes.append("- បន្ទាត់បេះដូង៖ អារម្មណ៍ជ្រាលជ្រៅ ស្មោះត្រង់ក្នុងទំនាក់ទំនង និងឱ្យតម្លៃការពិត។")
        elif _has_any(text, [r"ខ្លី", r"short"]):
            notes.append("- បន្ទាត់បេះដូងខ្លី៖ បង្ហាញការប្រុងប្រយ័ត្នចំពោះស្នេហា ត្រូវបើកចិត្តនិយាយច្បាស់។")
        if _has_any(text, [r"ខូច", r"ដាច់", r"break"]):
            notes.append("- បន្ទាត់បេះដូងមានចន្លោះ៖ ទំនាក់ទំនងអាចមានវគ្គផ្លាស់ប្ដូរ ត្រូវអត់ធ្មត់និងស្មោះត្រង់។")

    if _has_any(text, [r"បន្ទាត់ជីវិត", r"life line"]):
        if _has_any(text, [r"ជ្រៅ", r"deep", r"ច្បាស់", r"វែង", r"long"]):
            notes.append("- បន្ទាត់ជីវិត៖ ថាមពលល្អ និងការរស់នៅមានគោលដៅ។")
        if _has_any(text, [r"ខ្លី", r"short"]):
            notes.append("- បន្ទាត់ជីវិតខ្លី៖ ប្រាប់ពីចំណង់ឯករាជ្យ និងសម្រេចចិត្តដោយខ្លួនឯង មិនមែនទាយអាយុទេ។")
        if _has_any(text, [r"ខូច", r"ដាច់", r"break"]):
            notes.append("- បន្ទាត់ជីវិតមានចន្លោះ៖ មានដំណាក់កាលប្ដូរផ្លូវជីវិត ត្រូវគ្រប់គ្រងកម្លាំង និងសម្រាកឱ្យគ្រប់។")

    if _has_any(text, [r"បន្ទាត់វាសនា", r"fate line", r"line of destiny"]):
        notes.append("- បន្ទាត់វាសនា៖ បង្ហាញឥទ្ធិពលបរិបទក្រៅលើការងារ និងផ្លូវជីវិត។")
        if _has_any(text, [r"ច្បាស់", r"ជ្រៅ", r"វែង", r"clear"]):
            notes.append("- បន្ទាត់វាសនាច្បាស់៖ មានទិសដៅការងារច្បាស់ និងចូលចិត្តដើរតាមផែនការ។")
        if _has_any(text, [r"ផ្លាស់", r"changed", r"ខុសពីមុន"]):
            notes.append("- បន្ទាត់វាសនាប្រែប្រួល៖ ជាសញ្ញាដំណាក់កាលថ្មី (ការងារ ឬជីវិតផ្ទាល់ខ្លួន)។")

    if _has_any(text, [r"sun line", r"apollo", r"បន្ទាត់ព្រះអាទិត្យ"]):
        notes.append("- បន្ទាត់ព្រះអាទិត្យ៖ ទាក់ទងកេរ្តិ៍ឈ្មោះ ស្នាដៃ និងភាពជោគជ័យដែលគេមើលឃើញ។")

    notes.append("- ចំណាំ៖ ការមើលបាតដៃជាការណែនាំទូទៅ ប្រាប់ទំនោរ មិនកំណត់អនាគតដាច់ខាត។")
    return "\n".join(notes)

