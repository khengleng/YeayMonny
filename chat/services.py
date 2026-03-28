from __future__ import annotations

import base64
import difflib
import io
import re
from typing import Iterable

from django.conf import settings
from django.utils import timezone
from openai import OpenAI
from openai import OpenAIError

from .astrology import build_astrology_snapshot
from .birth_weight import build_birth_weight_snapshot
from .compatibility import build_compatibility_snapshot
from .face_reading import build_face_reading_engine_notes
from .financial_advisory import build_financial_advisory_snapshot
from .fengshui import build_fengshui_snapshot
from .house_numerology import build_house_numerology_snapshot
from .lucky_signs import build_lucky_signs_snapshot
from .models import AssistantConfig, Message
from .palm_reading import build_palm_reading_engine_notes
from .prompts import SYSTEM_PROMPT
from .vehicle_numerology import build_vehicle_numerology_snapshot

KHMER_GUARD_PROMPT = """
ច្បាប់ភាសាខ្លាំង
- ត្រូវឆ្លើយតែជាភាសាខ្មែរ ប៉ុណ្ណោះ
- កុំប្រើអក្សរឡាតាំង (A-Z, a-z) ក្នុងចម្លើយ
- កុំប្រើប្រយោគភាសាអង់គ្លេស
- ប្រើពាក្យសាមញ្ញ ងាយយល់
- ត្រូវហៅអ្នកប្រើថា "ចៅ" ជានិច្ច
"""
ANTI_REPETITION_GUARD_PROMPT = """
ច្បាប់មិនឱ្យឆ្លើយដដែលៗ
- រាល់ចម្លើយត្រូវប្តូរពាក្យបើក និងពាក្យបិទ
- កុំប្រើឃ្លាដដែលៗរៀងរាល់លើក
- កុំឆ្លើយជាទម្រង់ដដែលទាំងអស់
- ប្រែប្ដូររបៀបណែនាំ៖ ពេលខ្លះផ្នែកអារម្មណ៍ ពេលខ្លះផ្នែកជាក់ស្តែង ពេលខ្លះដាស់តឿន
- ចូលបញ្ចូលព័ត៌មានអ្នកសួរ (ឈ្មោះ ថ្ងៃកំណើត ស្ថានភាព) បើមាន
- កុំឱ្យលេខល្អ ពណ៌ល្អ ទិសល្អ ដូចគ្នាជានិច្ច
- សម្លេងនៅតែជាយាយមុន្នី: ទន់ភ្លន់ កក់ក្តៅ មានបទពិសោធន៍
"""
IDENTITY_CONTEXT_GUARD_PROMPT = """
អត្តសញ្ញាណ និងបរិបទ
- អ្នកគឺយាយមុន្នី អ្នកមើលជោគជាតាបែបខ្មែរ និងចិនតែប៉ុណ្ណោះ
- កុំបញ្ចូលរបៀបមើលផ្សេងក្រៅពីខ្មែរ និងចិន
- អ្នកកំពុងជជែកតាម chat មិនមែនជួបផ្ទាល់
- កុំណែនាំឱ្យអ្នកប្រើមកជួបផ្ទាល់ ឬមកទីតាំងណាមួយ
"""
HIGH_EQ_GUARD_PROMPT = """
សម្លេងមនុស្ស និង EQ ខ្ពស់
- ស្ដាប់អារម្មណ៍អ្នកសួរ មុនផ្តល់ដំបូន្មាន
- ប្រើពាក្យលួងលោម យល់ចិត្ត មិនរឹងពេក
- ឆ្លើយឱ្យមានអារម្មណ៍ថាយាយកំពុងគិតសមនឹងស្ថានភាពពិតរបស់គាត់
- កុំឆ្លើយបែបម៉ាស៊ីន ឬជាបញ្ជីដដែលៗ
- បើអ្នកប្រើបារម្ភ ឬតានតឹង ត្រូវដាក់ពាក្យបន្ថយសម្ពាធជាមុន
"""
SHORT_RELEVANT_GUARD_PROMPT = """
ច្បាប់ចម្លើយខ្លី និងចំប្រធានបទ
- ឆ្លើយខ្លី សាមញ្ញ ងាយយល់
- ឆ្លើយតែអ្វីដែលទាក់ទងសំណួរអ្នកប្រើ
- កុំបន្ថែមព័ត៌មានមិនចាំបាច់
- បើមិនមានទិន្នន័យគ្រប់គ្រាន់ សួរតែ១សំណួរខ្លីដើម្បីបញ្ជាក់
"""
BIRTH_WEIGHT_SAFETY_PROMPT = """
ច្បាប់ទម្ងន់កំណើត (សំខាន់)
- "ទម្ងន់កំណើត" នៅទីនេះ ជាវិធីទស្សន៍ទាយបែបបុរាណ (liang/qian) ប៉ុណ្ណោះ
- មិនមែនការពិនិត្យឆ្អឹង ឬពិនិត្យវេជ្ជសាស្ត្រ
- កុំប្រើពាក្យដូចជា "ឆ្អឹងរឹងមាំ", "ឆ្អឹងខ្សោយ", "ជំងឺឆ្អឹង"
- កុំធ្វើរោគវិនិច្ឆ័យសុខភាព
"""
KHMER_ONLY_FALLBACK = "ចៅអើយ សូមទោស។ យាយនឹងឆ្លើយជាភាសាខ្មែរប៉ុណ្ណោះ។ សូមសួរម្តងទៀត។"
LUCKY_SIGNS_ON_DEMAND_PROMPT = """
ច្បាប់សញ្ញាសំណាង
- កុំបង្ហាញលេខល្អ ពណ៌ល្អ ទិសល្អ ឬថ្ងៃល្អ ដោយស្វ័យប្រវត្តិ
- បង្ហាញតែពេលអ្នកប្រើសួរដោយផ្ទាល់អំពី៖ លេខល្អ ពណ៌ល្អ ទិសល្អ ថ្ងៃល្អ ឬសំណាង
"""


def _is_birth_weight_question(*, question_focus: str, latest_user_text: str) -> bool:
    text = f"{question_focus}\n{latest_user_text}"
    return bool(
        re.search(
            r"(ទម្ងន់កំណើត|astrological weight|weight at birth|birth weight|wofs.*weight)",
            text,
            flags=re.IGNORECASE,
        )
    )


def _wants_lucky_signs(*, question_focus: str, latest_user_text: str) -> bool:
    text = f"{question_focus}\n{latest_user_text}"
    return bool(
        re.search(
            r"(លេខល្អ|ពណ៌ល្អ|ទិសល្អ|ថ្ងៃល្អ|សំណាង|lucky number|lucky color|lucky direction|lucky day)",
            text,
            flags=re.IGNORECASE,
        )
    )


def _build_profile_context(user_profile: dict[str, str] | None, config: AssistantConfig) -> str:
    profile = user_profile or {}
    name = (profile.get("name") or "").strip()
    birth_info = (profile.get("birth_info") or "").strip()
    question_focus = (profile.get("question_focus") or "").strip()
    latest_user_text = (profile.get("latest_user_text") or "").strip()
    snapshot = build_astrology_snapshot(birth_info)
    reference_date = timezone.localdate()
    birth_weight = build_birth_weight_snapshot(birth_info)
    engine_source_text = f"{question_focus}\n{latest_user_text}"
    feng = (
        build_fengshui_snapshot(birth_info, partner_birth_info=question_focus)
        if config.enable_fengshui_engine
        else None
    )
    vehicle = (
        build_vehicle_numerology_snapshot(
            engine_source_text,
            life_path_number=snapshot.life_path_number,
        )
        if config.enable_vehicle_numerology_engine
        else None
    )
    house = build_house_numerology_snapshot(engine_source_text) if config.enable_house_numerology_engine else None
    compatibility = (
        build_compatibility_snapshot(
            user_birth_info=birth_info,
            question_focus=question_focus,
            latest_user_text=latest_user_text,
        )
        if config.enable_compatibility_engine
        else None
    )
    finance = (
        build_financial_advisory_snapshot(
            question_focus=question_focus,
            latest_user_text=latest_user_text,
            life_path_number=snapshot.life_path_number,
        )
        if config.enable_financial_advisory_engine
        else None
    )
    lucky_signs = build_lucky_signs_snapshot(
        birth_info=birth_info,
        question_focus=question_focus,
        latest_user_text=latest_user_text,
        feng=feng,
    )
    include_lucky_signs = _wants_lucky_signs(question_focus=question_focus, latest_user_text=latest_user_text)

    astrology_lines = []
    if snapshot.year:
        astrology_lines.append(f"- ឆ្នាំកំណើត (គណនា)៖ {snapshot.year}")
    if snapshot.chinese_animal:
        astrology_lines.append(f"- ឆ្នាំចិន៖ {snapshot.chinese_animal}")
    if snapshot.age_years is not None:
        astrology_lines.append(f"- អាយុគិតត្រឹមថ្ងៃនេះ (គណនា)៖ {snapshot.age_years} ឆ្នាំ")
    if snapshot.western_sign:
        astrology_lines.append(f"- សញ្ញាផ្កាយ៖ {snapshot.western_sign}")
    if snapshot.life_path_number:
        astrology_lines.append(f"- លេខផ្លូវជីវិត៖ {snapshot.life_path_number}")
    if birth_weight.total_weight is not None:
        astrology_lines.append(f"- ទម្ងន់កំណើត (លាំង/ឈៀន)៖ {birth_weight.total_weight}")
    if birth_weight.result_label:
        astrology_lines.append(f"- លទ្ធផលទម្ងន់កំណើត៖ {birth_weight.result_label}")
    if birth_weight.note:
        astrology_lines.append(f"- សេចក្តីណែនាំទម្ងន់កំណើត៖ {birth_weight.note}")
    if birth_weight.total_weight is None:
        astrology_lines.append("- ទម្ងន់កំណើត៖ ត្រូវការថ្ងៃខែឆ្នាំកំណើតពេញ និងម៉ោងកំណើត (បើមាន)")
    astrology_block = "\n".join(astrology_lines) if astrology_lines else "- មិនទាន់គណនាបាន (ទិន្នន័យកំណើតមិនគ្រប់)"

    feng_lines = []
    if feng and feng.stem_name and feng.branch_name:
        feng_lines.append(f"- ឆ្នាំបែបចិន (ធាតុដើម)៖ {feng.stem_name}-{feng.branch_name}")
    if feng and feng.element:
        feng_lines.append(f"- ធាតុឆ្នាំ៖ {feng.element}")
    if feng and feng.kua_male:
        feng_lines.append(f"- លេខក្វាប្រុស (WOFS)៖ {feng.kua_male}")
    if feng and feng.kua_female:
        feng_lines.append(f"- លេខក្វាស្រី (WOFS)៖ {feng.kua_female}")
    if feng and feng.favorable_directions_male:
        feng_lines.append(f"- ទិសល្អក្វាប្រុស៖ {', '.join(feng.favorable_directions_male)}")
    if feng and feng.favorable_directions_female:
        feng_lines.append(f"- ទិសល្អក្វាស្រី៖ {', '.join(feng.favorable_directions_female)}")
    if feng and feng.caution_directions_male:
        feng_lines.append(f"- ទិសត្រូវប្រយ័ត្នក្វាប្រុស៖ {', '.join(feng.caution_directions_male)}")
    if feng and feng.caution_directions_female:
        feng_lines.append(f"- ទិសត្រូវប្រយ័ត្នក្វាស្រី៖ {', '.join(feng.caution_directions_female)}")
    if feng and feng.lucky_colors:
        feng_lines.append(f"- ពណ៌សមធាតុ៖ {', '.join(feng.lucky_colors)}")
    if feng and feng.harmony_animals:
        feng_lines.append(f"- ឆ្នាំដែលសមគ្នា៖ {', '.join(feng.harmony_animals)}")
    if feng and feng.clash_animal:
        feng_lines.append(f"- ឆ្នាំត្រូវប្រយ័ត្នប៉ះទង្គិច៖ {feng.clash_animal}")
    if feng and feng.annual_center_star:
        feng_lines.append(f"- Flying Star ប្រចាំឆ្នាំ (កណ្ដាល)៖ {feng.annual_center_star}")
    if feng and feng.annual_good_sectors:
        feng_lines.append(f"- ទិសល្អប្រចាំឆ្នាំ៖ {', '.join(feng.annual_good_sectors)}")
    if feng and feng.annual_caution_sectors:
        feng_lines.append(f"- ទិសត្រូវប្រយ័ត្នប្រចាំឆ្នាំ៖ {', '.join(feng.annual_caution_sectors)}")
    if feng and feng.tai_sui_direction:
        feng_lines.append(f"- ទិសតៃសួយឆ្នាំនេះ៖ {feng.tai_sui_direction}")
    if feng and feng.sui_po_direction:
        feng_lines.append(f"- ទិសប៉ះតៃសួយ (Sui Po)៖ {feng.sui_po_direction}")
    if feng and feng.ben_ming_nian:
        feng_lines.append("- ឆ្នាំនេះជាវដ្តដដែល (Ben Ming Nian)៖ ត្រូវធ្វើអ្វីៗស្ងប់ៗ និងប្រុងប្រយ័ត្នបន្ថែម")
    if feng and feng.four_apart_animals:
        feng_lines.append(f"- ឆ្នាំសមតាមចន្លោះ៤ឆ្នាំ (TravelChinaGuide style)៖ {', '.join(feng.four_apart_animals)}")
    if feng and feng.three_apart_animals:
        feng_lines.append(f"- ឆ្នាំងាយខ្វែងគំនិតតាមចន្លោះ៣ឆ្នាំ៖ {', '.join(feng.three_apart_animals)}")
    if feng and feng.partner_animal and feng.partner_relation:
        feng_lines.append(f"- ទំនាក់ទំនងជាមួយឆ្នាំ {feng.partner_animal}៖ {feng.partner_relation}")
    if not config.enable_fengshui_engine:
        feng_block = "- ម៉ាស៊ីន Feng Shui ត្រូវបានបិទដោយ Operator"
    else:
        feng_block = "\n".join(feng_lines) if feng_lines else "- មិនទាន់គណនា WOFS បាន (ទិន្នន័យកំណើតមិនគ្រប់)"

    vehicle_lines = []
    if vehicle and vehicle.plate_raw:
        vehicle_lines.append(f"- ផ្លាកលេខរកឃើញ៖ {vehicle.plate_raw}")
    if vehicle and vehicle.total_value:
        vehicle_lines.append(f"- ផលបូកលេខសរុប៖ {vehicle.total_value}")
    if vehicle and vehicle.root_number:
        vehicle_lines.append(f"- លេខគោលរថយន្ត៖ {vehicle.root_number}")
    if vehicle and vehicle.meaning:
        vehicle_lines.append(f"- អត្ថន័យ៖ {vehicle.meaning}")
    if vehicle and vehicle.compatibility_hint:
        vehicle_lines.append(f"- ភាពសមគ្នា៖ {vehicle.compatibility_hint}")
    if not config.enable_vehicle_numerology_engine:
        vehicle_block = "- ម៉ាស៊ីនលេខផ្លាករថយន្តត្រូវបានបិទដោយ Operator"
    else:
        vehicle_block = "\n".join(vehicle_lines) if vehicle_lines else "- មិនទាន់មានផ្លាកលេខសម្រាប់គណនា"

    house_lines = []
    if house and house.raw_candidate:
        house_lines.append(f"- លេខអាសយដ្ឋានរកឃើញ៖ {house.raw_candidate}")
    if house and house.moving_part:
        house_lines.append(f"- លេខប្រើគណនា (moving number)៖ {house.moving_part}")
    if house and house.total_value:
        house_lines.append(f"- ផលបូកលេខសរុប៖ {house.total_value}")
    if house and house.root_number:
        house_lines.append(f"- លេខគោលផ្ទះ៖ {house.root_number}")
    if house and house.meaning:
        house_lines.append(f"- អត្ថន័យ៖ {house.meaning}")
    if house and house.caution:
        house_lines.append(f"- ចំណាំប្រុងប្រយ័ត្ន៖ {house.caution}")
    if not config.enable_house_numerology_engine:
        house_block = "- ម៉ាស៊ីនលេខផ្ទះត្រូវបានបិទដោយ Operator"
    else:
        house_block = "\n".join(house_lines) if house_lines else "- មិនទាន់មានលេខផ្ទះសម្រាប់គណនា"

    comp_lines = []
    if compatibility and compatibility.partner_birth_info:
        comp_lines.append(f"- ឆ្នាំ/ថ្ងៃកំណើតគូ (រកឃើញ)៖ {compatibility.partner_birth_info}")
    if compatibility and compatibility.partner_animal:
        comp_lines.append(f"- ឆ្នាំចិនគូស្នេហ៍៖ {compatibility.partner_animal}")
    if compatibility and compatibility.partner_western_sign:
        comp_lines.append(f"- សញ្ញាផ្កាយគូស្នេហ៍៖ {compatibility.partner_western_sign}")
    if compatibility and compatibility.relation_stage:
        comp_lines.append(f"- ស្ថានភាពទំនាក់ទំនង៖ {compatibility.relation_stage}")
    if compatibility and compatibility.intent:
        comp_lines.append(f"- ចេតនាសំណួរ៖ {compatibility.intent}")
    if compatibility and compatibility.score is not None:
        comp_lines.append(f"- ពិន្ទុភាពត្រូវគ្នា (០-១០០)៖ {compatibility.score}")
    if compatibility and compatibility.level:
        comp_lines.append(f"- កម្រិតសរុប៖ {compatibility.level}")
    if compatibility and compatibility.key_notes:
        comp_lines.append(f"- ចំណុចសំខាន់៖ {' | '.join(compatibility.key_notes)}")
    if compatibility and compatibility.guidance:
        comp_lines.append(f"- ដំបូន្មាន៖ {compatibility.guidance}")
    if not config.enable_compatibility_engine:
        comp_block = "- ម៉ាស៊ីនភាពត្រូវគ្នាស្នេហាត្រូវបានបិទដោយ Operator"
    else:
        comp_block = "\n".join(comp_lines) if comp_lines else "- មិនទាន់មានទិន្នន័យគូស្នេហ៍សម្រាប់គណនា"

    finance_lines = []
    if finance and finance.focus_area:
        finance_lines.append(f"- ផ្នែកហិរញ្ញវត្ថុចម្បង៖ {finance.focus_area}")
    if finance and finance.risk_level:
        finance_lines.append(f"- កម្រិតហានិភ័យ៖ {finance.risk_level}")
    if finance and finance.actions:
        finance_lines.append(f"- ជំហានណែនាំ៖ {' | '.join(finance.actions)}")
    if finance and finance.caution:
        finance_lines.append(f"- ចំណាំ៖ {finance.caution}")
    if not config.enable_financial_advisory_engine:
        finance_block = "- ម៉ាស៊ីនណែនាំហិរញ្ញវត្ថុត្រូវបានបិទដោយ Operator"
    else:
        finance_block = "\n".join(finance_lines) if finance_lines else "- មិនទាន់មានទិន្នន័យហិរញ្ញវត្ថុគ្រប់គ្រាន់"

    operator_note = (config.engine_operator_note or "").strip()
    operator_block = operator_note or "- គ្មាន"
    if include_lucky_signs:
        lucky_block = (
            f"- លេខល្អប្តូរតាមបរិបទ៖ {', '.join(str(n) for n in lucky_signs.lucky_numbers)}\n"
            f"- ពណ៌ល្អប្តូរតាមបរិបទ៖ {', '.join(lucky_signs.lucky_colors)}\n"
            f"- ទិសល្អប្តូរតាមបរិបទ៖ {', '.join(lucky_signs.lucky_directions)}\n"
            f"- ថ្ងៃល្អប្តូរតាមបរិបទ៖ {', '.join(lucky_signs.lucky_days)}"
        )
    else:
        lucky_block = "- កុំបង្ហាញសញ្ញាសំណាងក្នុងចម្លើយនេះ (អ្នកប្រើមិនបានសួរដោយផ្ទាល់)"

    return (
        "ប្រវត្តិអ្នកសួរ (ត្រូវយកមកគិតមុនឆ្លើយ)\n"
        f"- ឈ្មោះ៖ {name or 'មិនទាន់ប្រាប់'}\n"
        f"- ថ្ងៃ/ឆ្នាំកំណើត៖ {birth_info or 'មិនទាន់ប្រាប់'}\n"
        f"- ប្រធានបទចម្បង៖ {question_focus or 'មិនទាន់ប្រាប់'}\n\n"
        "ថ្ងៃយោងសម្រាប់គណនា (Runtime)\n"
        f"- ថ្ងៃបច្ចុប្បន្នក្នុងប្រព័ន្ធ៖ {reference_date.isoformat()}\n"
        f"- ឆ្នាំបច្ចុប្បន្នសម្រាប់គណនា៖ {reference_date.year}\n\n"
        "លទ្ធផលគណនាហោរាទូទៅពីទិន្នន័យកំណើត\n"
        f"{astrology_block}\n\n"
        "លទ្ធផលគណនា Feng Shui (WOFS style)\n"
        f"{feng_block}\n\n"
        "លទ្ធផលគណនាផ្លាកលេខរថយន្ត (Numerology)\n"
        f"{vehicle_block}\n\n"
        "លទ្ធផលគណនាលេខផ្ទះ (Numerology)\n"
        f"{house_block}\n\n"
        "លទ្ធផលគណនាភាពត្រូវគ្នាស្នេហា (Compatibility Engine)\n"
        f"{comp_block}\n\n"
        "លទ្ធផលណែនាំហិរញ្ញវត្ថុ (Financial Advisory Engine)\n"
        f"{finance_block}\n\n"
        "សញ្ញាសំណាងប្តូរតាមបរិបទ (Dynamic Lucky Signs)\n"
        f"{lucky_block}\n\n"
        "កំណត់ចំណាំប្រតិបត្តិការ (Operator)\n"
        f"{operator_block}\n\n"
        "ច្បាប់បន្ថែម\n"
        "- មុនឆ្លើយ ត្រូវយកប្រវត្តិនេះមកសម្របសំឡេងឱ្យសមមនុស្សនោះ\n"
        "- បើទិន្នន័យខ្វះ សូមសួរបន្ថែមដោយទន់ភ្លន់\n"
        "- កុំឆ្លើយទូទៅពេក បើមានប្រវត្តិរួចហើយ\n"
        "- ត្រូវហៅអ្នកប្រើថា 'ចៅ' ជានិច្ច\n"
        "- ការគណនាអាយុ ត្រូវយោងតាមថ្ងៃបច្ចុប្បន្នក្នុងប្រព័ន្ធខាងលើ មិនត្រូវទាយឆ្នាំដោយខ្លួនឯង\n"
        "- បើអ្នកប្រើមិនបានសួរសំណាងដោយផ្ទាល់ កុំដាក់លេខ/ពណ៌/ទិស/ថ្ងៃល្អ\n"
        "- ពេលអ្នកប្រើសួរ លេខ/ពណ៌/ទិស/ថ្ងៃល្អ ត្រូវយោងតាមសញ្ញាសំណាងប្តូរតាមបរិបទខាងលើ មិនឱ្យដដែលជានិច្ច\n"
        f"- កម្រិតពិន្ទុភាពត្រូវគ្នា ({config.compatibility_score_threshold}) ជាតម្លៃយោងបកស្រាយ មិនមែនការកំណត់ដាច់ខាត\n"
        "- កុំអះអាងថាជាលទ្ធផលផ្លូវការ ឬ ១០០% ត្រឹមត្រូវ; ប្រើជាការណែនាំទូទៅ"
    )


def _build_messages(
    history: Iterable[Message],
    system_prompt: str,
    user_profile: dict[str, str] | None = None,
    config: AssistantConfig | None = None,
) -> list[dict[str, str]]:
    active_config = config or AssistantConfig.get_solo()
    history_list = list(history)
    latest_user_text = ""
    for item in reversed(history_list):
        if item.role == Message.Role.USER and item.content:
            latest_user_text = item.content
            break
    profile_with_latest = {
        **(user_profile or {}),
        "latest_user_text": latest_user_text,
    }
    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "system", "content": _build_profile_context(profile_with_latest, active_config)},
        {"role": "system", "content": KHMER_GUARD_PROMPT.strip()},
        {"role": "system", "content": ANTI_REPETITION_GUARD_PROMPT.strip()},
        {"role": "system", "content": LUCKY_SIGNS_ON_DEMAND_PROMPT.strip()},
        {"role": "system", "content": IDENTITY_CONTEXT_GUARD_PROMPT.strip()},
        {"role": "system", "content": HIGH_EQ_GUARD_PROMPT.strip()},
        {"role": "system", "content": SHORT_RELEVANT_GUARD_PROMPT.strip()},
        {"role": "system", "content": BIRTH_WEIGHT_SAFETY_PROMPT.strip()},
    ]
    for item in history_list:
        messages.append({"role": item.role, "content": item.content})
    return messages


ASCII_TO_KHMER_DIGITS = str.maketrans("0123456789", "០១២៣៤៥៦៧៨៩")


def _khmer_num(value: str) -> str:
    return value.translate(ASCII_TO_KHMER_DIGITS)


def _build_birth_weight_reply(user_profile: dict[str, str] | None) -> str:
    profile = user_profile or {}
    birth_info = (profile.get("birth_info") or "").strip()
    snapshot = build_birth_weight_snapshot(birth_info)
    if snapshot.total_weight is None:
        return (
            "ចៅអើយ សម្រាប់គណនាទម្ងន់កំណើតបែបទស្សន៍ទាយ "
            "សូមផ្តល់ថ្ងៃ-ខែ-ឆ្នាំកំណើតពេញ និងម៉ោងកំណើត។"
        )

    total = _khmer_num(f"{snapshot.total_weight:.1f}")
    label = snapshot.result_label or "មធ្យម"
    note = snapshot.note or "ធ្វើការសម្រេចចិត្តឱ្យស្ងប់ និងមានផែនការ។"
    return (
        f"ចៅអើយ ទម្ងន់កំណើតបែបទស្សន៍ទាយរបស់ចៅគឺ {total} លាំង។ "
        f"ន័យសរុប៖ {label}។ {note}"
    )


def _build_calculation_basis_line(user_profile: dict[str, str] | None) -> str:
    profile = user_profile or {}
    birth_info = (profile.get("birth_info") or "").strip()
    ref_date = timezone.localdate()
    ref_text = _khmer_num(f"{ref_date.day:02d}-{ref_date.month:02d}-{ref_date.year}")
    snapshot = build_astrology_snapshot(birth_info, reference_date=ref_date)

    if snapshot.year and snapshot.month and snapshot.day:
        dob_text = _khmer_num(f"{snapshot.day:02d}-{snapshot.month:02d}-{snapshot.year}")
        if snapshot.age_years is not None:
            age_text = _khmer_num(str(snapshot.age_years))
            return f"មូលដ្ឋានគណនា៖ ថ្ងៃកំណើត {dob_text} | ថ្ងៃយោង {ref_text} | អាយុគណនា {age_text} ឆ្នាំ"
        return f"មូលដ្ឋានគណនា៖ ថ្ងៃកំណើត {dob_text} | ថ្ងៃយោង {ref_text}"

    if snapshot.year:
        year_text = _khmer_num(str(snapshot.year))
        return (
            f"មូលដ្ឋានគណនា៖ មានតែឆ្នាំកំណើត {year_text} | ថ្ងៃយោង {ref_text} | "
            "សូមផ្តល់ថ្ងៃ-ខែ-ឆ្នាំកំណើតពេញ ដើម្បីគណនាអាយុឱ្យត្រឹមត្រូវ"
        )

    return (
        f"មូលដ្ឋានគណនា៖ មិនទាន់មានថ្ងៃខែឆ្នាំកំណើតពេញ | ថ្ងៃយោង {ref_text} | "
        "សូមផ្តល់ថ្ងៃ-ខែ-ឆ្នាំកំណើត ដើម្បីគណនាឱ្យច្បាស់"
    )


def _attach_calculation_basis(text: str, user_profile: dict[str, str] | None) -> str:
    content = (text or "").strip()
    if not content:
        return content
    profile = user_profile or {}
    question_focus = (profile.get("question_focus") or "").strip()
    latest_user_text = (profile.get("latest_user_text") or "").strip()
    if _is_birth_weight_question(question_focus=question_focus, latest_user_text=latest_user_text):
        return content
    wants_basis = bool(
        re.search(
            r"(អាយុ|គណនា|ថ្ងៃកំណើត|dob|birth|age)",
            f"{question_focus}\n{latest_user_text}",
            flags=re.IGNORECASE,
        )
    )
    if not wants_basis:
        return content
    basis = _build_calculation_basis_line(user_profile)
    if "មូលដ្ឋានគណនា" in content:
        return content
    return f"{content}\n\n{basis}"


def _build_openai_client() -> OpenAI:
    return OpenAI(api_key=settings.OPENAI_API_KEY, timeout=settings.OPENAI_TIMEOUT_SECONDS)


def transcribe_audio_bytes(*, filename: str, audio_bytes: bytes) -> str:
    if not settings.OPENAI_API_KEY or not audio_bytes:
        return ""

    client = _build_openai_client()
    audio_file = io.BytesIO(audio_bytes)
    audio_file.name = filename or "voice.ogg"
    model_candidates = [settings.OPENAI_TRANSCRIBE_MODEL, "whisper-1"]
    transcript = None
    for model_name in model_candidates:
        try:
            audio_file.seek(0)
            transcript = client.audio.transcriptions.create(
                model=model_name,
                file=audio_file,
            )
            break
        except OpenAIError:
            transcript = None
            continue
    if transcript is None:
        return ""

    text = (getattr(transcript, "text", "") or "").strip()
    return text


def analyze_image_bytes(*, filename: str, content_type: str, image_bytes: bytes, user_text: str = "") -> str:
    if not settings.OPENAI_API_KEY or not image_bytes:
        return ""

    model_name = settings.OPENAI_VISION_MODEL
    config = AssistantConfig.get_solo()
    mime = content_type or "image/jpeg"
    b64 = base64.b64encode(image_bytes).decode("utf-8")
    image_url = f"data:{mime};base64,{b64}"
    client = _build_openai_client()

    prompt = (
        "អ្នកជាយាយមុន្នី។ សូមមើលរូបនេះហើយសរសេរសេចក្តីសង្ខេបជាភាសាខ្មែរងាយៗ "
        "សម្រាប់ប្រើមើលជោគជាតាតាម chat។\n\n"
        "ចំណុចត្រូវធ្វើ៖\n"
        "1) បើជារូបមុខ (face)៖ សូមពិពណ៌នាសញ្ញាទូទៅដែលមើលឃើញពីមុខ ដូចជា ទឹកមុខ ភ្នែក ការបង្ហាញអារម្មណ៍ទូទៅ "
        "ហើយភ្ជាប់ជាការណែនាំជីវិតបែបទន់ភ្លន់ (មិនអះអាង១០០%)។\n"
        "2) បើជារូបបាតដៃ (palm)៖ សូមពិពណ៌នាបន្ទាត់/រាងទូទៅដែលមើលឃើញច្បាស់ "
        "ហើយភ្ជាប់ជាការណែនាំស្នេហា ការងារ លុយកាក់ បែបទូទៅ (មិនទុកចិត្តដាច់ខាត)។ "
        "សូមពិពណ៌នាឱ្យបានចំណុចបន្ទាត់សំខាន់៖ បន្ទាត់បេះដូង បន្ទាត់គំនិត បន្ទាត់ជីវិត បន្ទាត់វាសនា "
        "និងបន្ទាត់ព្រះអាទិត្យ (បើឃើញ)។\n"
        "3) បើមិនមែនមុខ ឬ បាតដៃ៖ សូមពិពណ៌នាសញ្ញាទូទៅក្នុងរូប "
        "ហើយបកស្រាយជាគន្លឹះមើលជោគជាតាបែបខ្មែរ+ចិន។\n"
        "4) បើរូបមិនច្បាស់៖ សូមនិយាយត្រង់ៗថាមិនច្បាស់ ហើយស្នើឱ្យផ្ញើរូបថ្មីច្បាស់ជាងមុន។\n\n"
        "ច្បាប់សំខាន់៖\n"
        "- ភាសាខ្មែរសាមញ្ញប៉ុណ្ណោះ\n"
        "- កុំប្រើពាក្យពិបាក\n"
        "- កុំបំភ័យ\n"
        "- កុំសន្យាលទ្ធផលដាច់ខាត\n"
        "- និយាយតែការណែនាំទូទៅ\n"
        "- បើជារូបមុខ សូមពិពណ៌នាចំណុច៖ ថ្ងាស ភ្នែក ច្រមុះ មាត់ ចង្កា ត្រចៀក ឱ្យច្បាស់"
    )
    if not config.enable_face_reading_engine:
        prompt += "\n- មិនត្រូវផ្តោតការមើលមុខជាលម្អិត (feature នេះបិទដោយ operator)"
    if not config.enable_palm_reading_engine:
        prompt += "\n- មិនត្រូវផ្តោតការមើលបាតដៃជាលម្អិត (feature នេះបិទដោយ operator)"
    if user_text:
        prompt += f"\n\nបរិបទសំណួររបស់អ្នកប្រើ៖ {user_text}"

    try:
        response = client.responses.create(
            model=model_name,
            input=[
                {
                    "role": "system",
                    "content": KHMER_GUARD_PROMPT.strip(),
                },
                {
                    "role": "system",
                    "content": IDENTITY_CONTEXT_GUARD_PROMPT.strip(),
                },
                {
                    "role": "system",
                    "content": HIGH_EQ_GUARD_PROMPT.strip(),
                },
                {
                    "role": "user",
                    "content": [
                        {"type": "input_text", "text": prompt},
                        {"type": "input_image", "image_url": image_url},
                    ],
                },
            ],
            temperature=0.4,
        )
    except OpenAIError:
        return ""

    text = (response.output_text or "").strip()
    face_notes = build_face_reading_engine_notes(text) if config.enable_face_reading_engine else ""
    palm_notes = build_palm_reading_engine_notes(text) if config.enable_palm_reading_engine else ""
    if face_notes:
        text = f"{text}\n\n{face_notes}".strip()
    if palm_notes:
        text = f"{text}\n\n{palm_notes}".strip()
    return text


def _looks_non_khmer(text: str) -> bool:
    latin_count = len(re.findall(r"[A-Za-z]", text))
    khmer_count = len(re.findall(r"[\u1780-\u17FF]", text))
    if khmer_count == 0:
        return True
    return latin_count > 4


def _enforce_grandchild_address(text: str) -> str:
    value = (text or "").strip()
    if not value:
        return value

    replacements = {
        "កូនអើយ": "ចៅអើយ",
        "កូនៗ": "ចៅៗ",
        "កូន ": "ចៅ ",
        " កូន": " ចៅ",
    }
    for src, dst in replacements.items():
        value = value.replace(src, dst)

    if "ចៅ" not in value:
        value = f"ចៅអើយ {value}"
    return value


def _enforce_short_reply(text: str) -> str:
    value = re.sub(r"\s+", " ", (text or "").strip())
    if not value:
        return value
    limit = max(50, int(getattr(settings, "MAX_ASSISTANT_REPLY_CHARS", 1200)))
    if len(value) <= limit:
        return value
    cut = value[:limit]
    # Prefer cutting at Khmer/latin sentence punctuation for readability.
    m = re.search(r"[។!?]\s+[^។!?]*$", cut)
    if m:
        cut = cut[: m.start() + 1]
    return cut.rstrip() + "…"


def _sanitize_birth_weight_language(text: str) -> str:
    value = (text or "").strip()
    if not value:
        return value

    value = value.replace("bone measurement", "វិធីទស្សន៍ទាយទម្ងន់កំណើត")
    value = value.replace("bone weight", "ទម្ងន់កំណើតបែបទស្សន៍ទាយ")
    value = value.replace("គ្លីនិក", "ការណែនាំទូទៅ")
    value = value.replace("វេជ្ជសាស្ត្រ", "ទស្សន៍ទាយ")
    value = value.replace("ឆ្អឹងរឹងមាំ", "ផ្លូវជីវិតមានកម្លាំង")
    value = value.replace("ឆ្អឹងខ្សោយ", "ត្រូវប្រុងប្រយ័ត្នជំហានជីវិត")
    value = value.replace("សុខភាពឆ្អឹង", "ស្ថានភាពជីវិត")
    value = re.sub(r"ពិនិត្យឆ្អឹង", "គណនាទម្ងន់កំណើត", value)
    value = re.sub(r"ជំងឺឆ្អឹង", "ផ្លូវជីវិតត្រូវប្រុងប្រយ័ត្ន", value)
    value = re.sub(r"bone density", "ទម្ងន់កំណើតបែបទស្សន៍ទាយ", value, flags=re.IGNORECASE)

    if "ទម្ងន់កំណើត" in value and "វិធីទស្សន៍ទាយ" not in value:
        value = f"{value}\n\nចំណាំ៖ ទម្ងន់កំណើតនេះជាវិធីទស្សន៍ទាយបុរាណ មិនមែនការពិនិត្យសុខភាពទេ។"
    return value


def _rewrite_to_khmer_only(*, client: OpenAI, model_name: str, text: str) -> str:
    response = client.responses.create(
        model=model_name,
        temperature=0.2,
        input=[
            {"role": "system", "content": KHMER_GUARD_PROMPT.strip()},
            {"role": "system", "content": IDENTITY_CONTEXT_GUARD_PROMPT.strip()},
            {"role": "system", "content": HIGH_EQ_GUARD_PROMPT.strip()},
            {
                "role": "user",
                "content": (
                    "សូមកែសម្រួលអត្ថបទខាងក្រោមឱ្យនៅតែអត្ថន័យដើម "
                    "ហើយឆ្លើយតែជាភាសាខ្មែរងាយៗ:\n\n"
                    f"{text}"
                ),
            },
        ],
    )
    return (response.output_text or "").strip()


def _normalize_for_similarity(text: str) -> str:
    compact = re.sub(r"\s+", " ", text).strip().lower()
    compact = re.sub(r"[^\u1780-\u17FFA-Za-z0-9 ]+", "", compact)
    return compact


def _token_set(text: str) -> set[str]:
    normalized = _normalize_for_similarity(text)
    if not normalized:
        return set()
    return {tok for tok in normalized.split(" ") if tok}


def _jaccard_similarity(a: str, b: str) -> float:
    sa = _token_set(a)
    sb = _token_set(b)
    if not sa or not sb:
        return 0.0
    return len(sa & sb) / len(sa | sb)


def _looks_repetitive_against_history(text: str, history: Iterable[Message]) -> bool:
    candidate = _normalize_for_similarity(text)
    if not candidate:
        return True

    assistant_texts = [
        _normalize_for_similarity(item.content)
        for item in history
        if item.role == Message.Role.ASSISTANT and item.content
    ]
    recent = assistant_texts[-5:]
    if candidate in recent:
        return True

    for prior in recent:
        if not prior:
            continue
        ratio = difflib.SequenceMatcher(None, candidate, prior).ratio()
        if ratio >= 0.86:
            return True
        if _jaccard_similarity(candidate, prior) >= 0.75:
            return True
    return False


def _rewrite_to_fresh_style(*, client: OpenAI, model_name: str, text: str, history: Iterable[Message]) -> str:
    recent_assistant = [
        item.content
        for item in history
        if item.role == Message.Role.ASSISTANT and item.content
    ][-5:]
    recent_block = "\n\n".join(recent_assistant) if recent_assistant else "(គ្មាន)"

    response = client.responses.create(
        model=model_name,
        temperature=0.7,
        input=[
            {"role": "system", "content": KHMER_GUARD_PROMPT.strip()},
            {"role": "system", "content": ANTI_REPETITION_GUARD_PROMPT.strip()},
            {"role": "system", "content": IDENTITY_CONTEXT_GUARD_PROMPT.strip()},
            {"role": "system", "content": HIGH_EQ_GUARD_PROMPT.strip()},
            {
                "role": "user",
                "content": (
                    "សូមសរសេរចម្លើយនេះឡើងវិញឱ្យថ្មី មិនស្ទួននឹងចម្លើយចាស់ៗ។ "
                    "ត្រូវឱ្យសម្លេងមានមនុស្សធម៌ និងយល់ចិត្តខ្ពស់។ "
                    "រក្សាអត្ថន័យដើម និងភាសាខ្មែរងាយៗ។\n\n"
                    f"ចម្លើយបច្ចុប្បន្ន:\n{text}\n\n"
                    f"ចម្លើយចាស់ៗថ្មីៗ:\n{recent_block}"
                ),
            },
        ],
    )
    return (response.output_text or "").strip()


def get_yeay_monny_reply(
    history: Iterable[Message],
    *,
    user_profile: dict[str, str] | None = None,
) -> str:
    if not settings.OPENAI_API_KEY:
        return "កូនអើយ ឥឡូវនេះយាយមិនទាន់ភ្ជាប់សេវាមើលជោគជាតាបានទេ។ សូមសាកម្តងទៀតបន្តិចក្រោយ។"

    config = AssistantConfig.get_solo()
    system_prompt = config.system_prompt or SYSTEM_PROMPT
    model_name = config.model_name or settings.OPENAI_MODEL
    temperature = config.temperature if config.temperature is not None else 0.8
    history_list = list(history)
    latest_user_text = ""
    for item in reversed(history_list):
        if item.role == Message.Role.USER and item.content:
            latest_user_text = item.content
            break
    profile = {
        **(user_profile or {}),
        "latest_user_text": latest_user_text,
    }
    question_focus = (profile.get("question_focus") or "").strip()
    if _is_birth_weight_question(question_focus=question_focus, latest_user_text=latest_user_text):
        text = _build_birth_weight_reply(profile)
        text = _enforce_grandchild_address(text)
        text = _enforce_short_reply(text)
        return _sanitize_birth_weight_language(text)

    client = _build_openai_client()
    try:
        response = client.responses.create(
            model=model_name,
            input=_build_messages(history_list, system_prompt, profile, config=config),
            temperature=temperature,
        )
    except OpenAIError:
        return "កូនអើយ យាយសូមទោស។ ឥឡូវនេះប្រព័ន្ធរវល់បន្តិច សូមសួរម្តងទៀតបន្តិចក្រោយ។"

    text = (response.output_text or "").strip()
    if text and _looks_non_khmer(text):
        try:
            rewritten = _rewrite_to_khmer_only(client=client, model_name=model_name, text=text)
            if rewritten and not _looks_non_khmer(rewritten):
                rewritten = _enforce_grandchild_address(rewritten)
                rewritten = _enforce_short_reply(rewritten)
                rewritten = _sanitize_birth_weight_language(rewritten)
                return _attach_calculation_basis(rewritten, user_profile)
        except OpenAIError:
            return KHMER_ONLY_FALLBACK
        return KHMER_ONLY_FALLBACK

    if text and _looks_repetitive_against_history(text, history):
        try:
            rewritten = _rewrite_to_fresh_style(
                client=client,
                model_name=model_name,
                text=text,
                history=history,
            )
            if rewritten and not _looks_non_khmer(rewritten) and not _looks_repetitive_against_history(rewritten, history):
                rewritten = _enforce_grandchild_address(rewritten)
                rewritten = _enforce_short_reply(rewritten)
                rewritten = _sanitize_birth_weight_language(rewritten)
                return _attach_calculation_basis(rewritten, user_profile)
        except OpenAIError:
            pass

    if text:
        text = _enforce_grandchild_address(text)
        text = _enforce_short_reply(text)
        text = _sanitize_birth_weight_language(text)
        return _attach_calculation_basis(text, user_profile)
    return "យាយសូមអភ័យទោស ចៅអើយ។ យាយមិនទាន់អាចឆ្លើយបានច្បាស់ទេ សូមសួរម្តងទៀត។"
