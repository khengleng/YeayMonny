from __future__ import annotations

import re


def _has_any(text: str, patterns: list[str]) -> bool:
    return any(re.search(pattern, text, flags=re.IGNORECASE) for pattern in patterns)


def _looks_like_face_reading_context(text: str) -> bool:
    if _has_any(
        text,
        [
            r"មិនឃើញមុខ",
            r"មិនមានមុខ",
            r"no face",
            r"not.*face",
        ],
    ):
        return False
    return _has_any(
        text,
        [
            r"មុខ",
            r"ផ្ទៃមុខ",
            r"face",
            r"forehead",
            r"eyes?",
            r"nose",
            r"mouth",
            r"chin",
            r"ear",
            r"ត្រចៀក",
            r"ភ្នែក",
            r"ច្រមុះ",
            r"មាត់",
            r"ចង្កា",
        ],
    )


def build_face_reading_engine_notes(observation_text: str) -> str:
    """
    Rule-based face reading helper inspired by classical face-reading structure
    (forehead/eyes/nose/mouth/chin zones) as presented by Lok Tin Feng Shui's
    face reading guidance page.
    """
    text = (observation_text or "").strip()
    if not text or not _looks_like_face_reading_context(text):
        return ""

    notes: list[str] = [
        "សេចក្ដីបកស្រាយបន្ថែមតាមចំណុចផ្ទៃមុខ",
    ]

    if _has_any(text, [r"ថ្ងាស", r"forehead", r"ទូលាយ", r"ភ្លឺ", r"ស្អាត"]):
        notes.append("- ថ្ងាស៖ ផ្លូវឱកាសដំបូងជីវិត (វ័យប្រហែល ១៥-៣០) មើលទៅមានអ្នកគាំទ្រនិងឱកាសល្អ។")

    if _has_any(text, [r"ភ្នែក", r"eyes?", r"ភ្លឺ", r"មើលច្បាស់", r"ស្ងប់"]):
        notes.append("- ភ្នែក៖ បង្ហាញពីចិត្ត និងការសម្រេចចិត្ត (វ័យប្រហែល ៣១-៤០)។ មើលទៅគិតច្បាស់និងមានមនុស្សធម៌។")
    elif _has_any(text, [r"នឿយ", r"អស់កម្លាំង", r"ស្រពេច", r"dull", r"tired"]):
        notes.append("- ភ្នែក៖ សញ្ញានឿយហត់ អារម្មណ៍ងាយរអិល។ គួរសម្រាក និងរៀបចំចិត្តឱ្យស្ងប់ជាមុន។")

    if _has_any(text, [r"ច្រមុះ", r"nose", r"ពេញ", r"ត្រង់", r"ច្បាស់"]):
        notes.append("- ច្រមុះ៖ ពាក់ព័ន្ធសំណាងហិរញ្ញវត្ថុ (វ័យប្រហែល ៤១-៥០)។ មើលទៅមានសមត្ថភាពគ្រប់គ្រងលុយបានល្អ។")
    if _has_any(text, [r"មូល", r"mole", r"ស្នាមខ្មៅ", r"ចំណុចខ្មៅ"]):
        notes.append("- ច្រមុះមានស្នាម/មូល៖ គួរប្រុងប្រយ័ត្នលុយហូរចេញ និងចំណាយតាមអារម្មណ៍។")

    if _has_any(text, [r"មាត់", r"mouth", r"បបូរ", r"សមស្រប", r"ពេញ"]):
        notes.append("- មាត់៖ ទាក់ទងការទំនាក់ទំនង និងគ្រួសារ (វ័យប្រហែល ៥១-៦០)។ និយាយទន់ភ្លន់នឹងនាំឱកាសល្អ។")
    elif _has_any(text, [r"ស្តើង", r"tight", r"ចង្អៀត", r"downturned"]):
        notes.append("- មាត់៖ ងាយមានការយល់ច្រឡំក្នុងការទាក់ទង។ ត្រូវនិយាយឱ្យច្បាស់ និងស្ងប់។")

    if _has_any(text, [r"ចង្កា", r"chin", r"មូល", r"ពេញ", r"រឹងមាំ"]):
        notes.append("- ចង្កា៖ ទាក់ទងស្ថេរភាពចុងជីវិត (៦១+)។ មើលទៅមានគ្រឹះគ្រួសារល្អ និងស្មារតីមាំ។")
    elif _has_any(text, [r"ស្រួច", r"pointed", r"ស្តើង"]):
        notes.append("- ចង្កា៖ ចុងវ័យត្រូវគិតផែនការសន្សំ និងសុខភាពឱ្យម៉ត់ចត់ជាងមុន។")

    if _has_any(text, [r"ត្រចៀក", r"ear", r"ធំ", r"ក្រាស់"]):
        notes.append("- ត្រចៀក៖ សញ្ញាថាមពល និងការគាំទ្រដំបូងជីវិត។ មើលទៅមានស្មារតីអត់ធ្មត់ល្អ។")

    if len(notes) == 1:
        notes.append("- រូបមុខមិនទាន់ច្បាស់គ្រប់ចំណុចទេ។ ចៅអាចផ្ញើរូបមុខច្បាស់មុខត្រង់ម្តងទៀត។")

    notes.append("- ចំណាំ៖ នេះជាការមើលទូទៅសម្រាប់ណែនាំប៉ុណ្ណោះ មិនមែនការកំណត់ដាច់ខាត។")
    return "\n".join(notes)
