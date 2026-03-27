from __future__ import annotations

import base64
import difflib
import io
import re
from typing import Iterable

from django.conf import settings
from openai import OpenAI
from openai import OpenAIError

from .astrology import build_astrology_snapshot
from .fengshui import build_fengshui_snapshot
from .models import AssistantConfig, Message
from .prompts import SYSTEM_PROMPT

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
KHMER_ONLY_FALLBACK = "ចៅអើយ សូមទោស។ យាយនឹងឆ្លើយជាភាសាខ្មែរប៉ុណ្ណោះ។ សូមសួរម្តងទៀត។"


def _build_profile_context(user_profile: dict[str, str] | None) -> str:
    profile = user_profile or {}
    name = (profile.get("name") or "").strip()
    birth_info = (profile.get("birth_info") or "").strip()
    question_focus = (profile.get("question_focus") or "").strip()
    snapshot = build_astrology_snapshot(birth_info)
    feng = build_fengshui_snapshot(birth_info)

    astrology_lines = []
    if snapshot.year:
        astrology_lines.append(f"- ឆ្នាំកំណើត (គណនា)៖ {snapshot.year}")
    if snapshot.chinese_animal:
        astrology_lines.append(f"- ឆ្នាំចិន៖ {snapshot.chinese_animal}")
    if snapshot.western_sign:
        astrology_lines.append(f"- សញ្ញាផ្កាយ៖ {snapshot.western_sign}")
    if snapshot.life_path_number:
        astrology_lines.append(f"- លេខផ្លូវជីវិត៖ {snapshot.life_path_number}")
    astrology_block = "\n".join(astrology_lines) if astrology_lines else "- មិនទាន់គណនាបាន (ទិន្នន័យកំណើតមិនគ្រប់)"

    feng_lines = []
    if feng.stem_name and feng.branch_name:
        feng_lines.append(f"- ឆ្នាំបែបចិន (ធាតុដើម)៖ {feng.stem_name}-{feng.branch_name}")
    if feng.element:
        feng_lines.append(f"- ធាតុឆ្នាំ៖ {feng.element}")
    if feng.kua_male:
        feng_lines.append(f"- លេខក្វាប្រុស (WOFS)៖ {feng.kua_male}")
    if feng.kua_female:
        feng_lines.append(f"- លេខក្វាស្រី (WOFS)៖ {feng.kua_female}")
    if feng.favorable_directions_male:
        feng_lines.append(f"- ទិសល្អក្វាប្រុស៖ {', '.join(feng.favorable_directions_male)}")
    if feng.favorable_directions_female:
        feng_lines.append(f"- ទិសល្អក្វាស្រី៖ {', '.join(feng.favorable_directions_female)}")
    if feng.caution_directions_male:
        feng_lines.append(f"- ទិសត្រូវប្រយ័ត្នក្វាប្រុស៖ {', '.join(feng.caution_directions_male)}")
    if feng.caution_directions_female:
        feng_lines.append(f"- ទិសត្រូវប្រយ័ត្នក្វាស្រី៖ {', '.join(feng.caution_directions_female)}")
    if feng.lucky_colors:
        feng_lines.append(f"- ពណ៌សមធាតុ៖ {', '.join(feng.lucky_colors)}")
    if feng.harmony_animals:
        feng_lines.append(f"- ឆ្នាំដែលសមគ្នា៖ {', '.join(feng.harmony_animals)}")
    if feng.clash_animal:
        feng_lines.append(f"- ឆ្នាំត្រូវប្រយ័ត្នប៉ះទង្គិច៖ {feng.clash_animal}")
    if feng.annual_center_star:
        feng_lines.append(f"- Flying Star ប្រចាំឆ្នាំ (កណ្ដាល)៖ {feng.annual_center_star}")
    if feng.annual_good_sectors:
        feng_lines.append(f"- ទិសល្អប្រចាំឆ្នាំ៖ {', '.join(feng.annual_good_sectors)}")
    if feng.annual_caution_sectors:
        feng_lines.append(f"- ទិសត្រូវប្រយ័ត្នប្រចាំឆ្នាំ៖ {', '.join(feng.annual_caution_sectors)}")
    if feng.tai_sui_direction:
        feng_lines.append(f"- ទិសតៃសួយឆ្នាំនេះ៖ {feng.tai_sui_direction}")
    if feng.sui_po_direction:
        feng_lines.append(f"- ទិសប៉ះតៃសួយ (Sui Po)៖ {feng.sui_po_direction}")
    feng_block = "\n".join(feng_lines) if feng_lines else "- មិនទាន់គណនា WOFS បាន (ទិន្នន័យកំណើតមិនគ្រប់)"

    return (
        "ប្រវត្តិអ្នកសួរ (ត្រូវយកមកគិតមុនឆ្លើយ)\n"
        f"- ឈ្មោះ៖ {name or 'មិនទាន់ប្រាប់'}\n"
        f"- ថ្ងៃ/ឆ្នាំកំណើត៖ {birth_info or 'មិនទាន់ប្រាប់'}\n"
        f"- ប្រធានបទចម្បង៖ {question_focus or 'មិនទាន់ប្រាប់'}\n\n"
        "លទ្ធផលគណនាហោរាទូទៅពីទិន្នន័យកំណើត\n"
        f"{astrology_block}\n\n"
        "លទ្ធផលគណនា Feng Shui (WOFS style)\n"
        f"{feng_block}\n\n"
        "ច្បាប់បន្ថែម\n"
        "- មុនឆ្លើយ ត្រូវយកប្រវត្តិនេះមកសម្របសំឡេងឱ្យសមមនុស្សនោះ\n"
        "- បើទិន្នន័យខ្វះ សូមសួរបន្ថែមដោយទន់ភ្លន់\n"
        "- កុំឆ្លើយទូទៅពេក បើមានប្រវត្តិរួចហើយ\n"
        "- ត្រូវហៅអ្នកប្រើថា 'ចៅ' ជានិច្ច\n"
        "- កុំអះអាងថាជាលទ្ធផលផ្លូវការ ឬ ១០០% ត្រឹមត្រូវ; ប្រើជាការណែនាំទូទៅ"
    )


def _build_messages(
    history: Iterable[Message],
    system_prompt: str,
    user_profile: dict[str, str] | None = None,
) -> list[dict[str, str]]:
    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "system", "content": _build_profile_context(user_profile)},
        {"role": "system", "content": KHMER_GUARD_PROMPT.strip()},
        {"role": "system", "content": ANTI_REPETITION_GUARD_PROMPT.strip()},
        {"role": "system", "content": IDENTITY_CONTEXT_GUARD_PROMPT.strip()},
        {"role": "system", "content": HIGH_EQ_GUARD_PROMPT.strip()},
    ]
    for item in history:
        messages.append({"role": item.role, "content": item.content})
    return messages


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
        "ហើយភ្ជាប់ជាការណែនាំស្នេហា ការងារ លុយកាក់ បែបទូទៅ (មិនទុកចិត្តដាច់ខាត)។\n"
        "3) បើមិនមែនមុខ ឬ បាតដៃ៖ សូមពិពណ៌នាសញ្ញាទូទៅក្នុងរូប "
        "ហើយបកស្រាយជាគន្លឹះមើលជោគជាតាបែបខ្មែរ+ចិន។\n"
        "4) បើរូបមិនច្បាស់៖ សូមនិយាយត្រង់ៗថាមិនច្បាស់ ហើយស្នើឱ្យផ្ញើរូបថ្មីច្បាស់ជាងមុន។\n\n"
        "ច្បាប់សំខាន់៖\n"
        "- ភាសាខ្មែរសាមញ្ញប៉ុណ្ណោះ\n"
        "- កុំប្រើពាក្យពិបាក\n"
        "- កុំបំភ័យ\n"
        "- កុំសន្យាលទ្ធផលដាច់ខាត\n"
        "- និយាយតែការណែនាំទូទៅ"
    )
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

    return (response.output_text or "").strip()


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

    client = _build_openai_client()
    try:
        response = client.responses.create(
            model=model_name,
            input=_build_messages(history, system_prompt, user_profile),
            temperature=temperature,
        )
    except OpenAIError:
        return "កូនអើយ យាយសូមទោស។ ឥឡូវនេះប្រព័ន្ធរវល់បន្តិច សូមសួរម្តងទៀតបន្តិចក្រោយ។"

    text = (response.output_text or "").strip()
    if text and _looks_non_khmer(text):
        try:
            rewritten = _rewrite_to_khmer_only(client=client, model_name=model_name, text=text)
            if rewritten and not _looks_non_khmer(rewritten):
                return _enforce_grandchild_address(rewritten)
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
                return _enforce_grandchild_address(rewritten)
        except OpenAIError:
            pass

    if text:
        return _enforce_grandchild_address(text)
    return "យាយសូមអភ័យទោស ចៅអើយ។ យាយមិនទាន់អាចឆ្លើយបានច្បាស់ទេ សូមសួរម្តងទៀត។"
