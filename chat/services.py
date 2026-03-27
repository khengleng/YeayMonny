from __future__ import annotations

import re
from typing import Iterable

from django.conf import settings
from openai import OpenAI
from openai import OpenAIError

from .models import AssistantConfig, Message
from .prompts import SYSTEM_PROMPT

KHMER_GUARD_PROMPT = """
ច្បាប់ភាសាខ្លាំង
- ត្រូវឆ្លើយតែជាភាសាខ្មែរ ប៉ុណ្ណោះ
- កុំប្រើអក្សរឡាតាំង (A-Z, a-z) ក្នុងចម្លើយ
- កុំប្រើប្រយោគភាសាអង់គ្លេស
- ប្រើពាក្យសាមញ្ញ ងាយយល់
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
KHMER_ONLY_FALLBACK = "កូនអើយ សូមទោស។ យាយនឹងឆ្លើយជាភាសាខ្មែរប៉ុណ្ណោះ។ សូមសួរម្តងទៀត។"


def _build_messages(history: Iterable[Message], system_prompt: str) -> list[dict[str, str]]:
    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "system", "content": KHMER_GUARD_PROMPT.strip()},
        {"role": "system", "content": ANTI_REPETITION_GUARD_PROMPT.strip()},
    ]
    for item in history:
        messages.append({"role": item.role, "content": item.content})
    return messages


def _looks_non_khmer(text: str) -> bool:
    latin_count = len(re.findall(r"[A-Za-z]", text))
    khmer_count = len(re.findall(r"[\u1780-\u17FF]", text))
    if khmer_count == 0:
        return True
    return latin_count > 4


def _rewrite_to_khmer_only(*, client: OpenAI, model_name: str, text: str) -> str:
    response = client.responses.create(
        model=model_name,
        temperature=0.2,
        input=[
            {"role": "system", "content": KHMER_GUARD_PROMPT.strip()},
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


def _looks_repetitive_against_history(text: str, history: Iterable[Message]) -> bool:
    candidate = " ".join(text.split()).strip()
    if not candidate:
        return True

    assistant_texts = [
        " ".join(item.content.split()).strip()
        for item in history
        if item.role == Message.Role.ASSISTANT and item.content
    ]
    recent = assistant_texts[-5:]
    return candidate in recent


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
            {
                "role": "user",
                "content": (
                    "សូមសរសេរចម្លើយនេះឡើងវិញឱ្យថ្មី មិនស្ទួននឹងចម្លើយចាស់ៗ។ "
                    "រក្សាអត្ថន័យដើម និងភាសាខ្មែរងាយៗ។\n\n"
                    f"ចម្លើយបច្ចុប្បន្ន:\n{text}\n\n"
                    f"ចម្លើយចាស់ៗថ្មីៗ:\n{recent_block}"
                ),
            },
        ],
    )
    return (response.output_text or "").strip()


def get_yeay_monny_reply(history: Iterable[Message]) -> str:
    if not settings.OPENAI_API_KEY:
        return "កូនអើយ ឥឡូវនេះយាយមិនទាន់ភ្ជាប់សេវាមើលជោគជាតាបានទេ។ សូមសាកម្តងទៀតបន្តិចក្រោយ។"

    config = AssistantConfig.get_solo()
    system_prompt = config.system_prompt or SYSTEM_PROMPT
    model_name = config.model_name or settings.OPENAI_MODEL
    temperature = config.temperature if config.temperature is not None else 0.8

    client = OpenAI(api_key=settings.OPENAI_API_KEY, timeout=settings.OPENAI_TIMEOUT_SECONDS)
    try:
        response = client.responses.create(
            model=model_name,
            input=_build_messages(history, system_prompt),
            temperature=temperature,
        )
    except OpenAIError:
        return "កូនអើយ យាយសូមទោស។ ឥឡូវនេះប្រព័ន្ធរវល់បន្តិច សូមសួរម្តងទៀតបន្តិចក្រោយ។"

    text = (response.output_text or "").strip()
    if text and _looks_non_khmer(text):
        try:
            rewritten = _rewrite_to_khmer_only(client=client, model_name=model_name, text=text)
            if rewritten and not _looks_non_khmer(rewritten):
                return rewritten
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
                return rewritten
        except OpenAIError:
            pass

    if text:
        return text
    return "យាយសូមអភ័យទោស កូនអើយ។ យាយមិនទាន់អាចឆ្លើយបានច្បាស់ទេ សូមសួរម្តងទៀត។"
