from __future__ import annotations

from typing import Iterable

from django.conf import settings
from openai import OpenAI
from openai import OpenAIError

from .models import AssistantConfig, Message
from .prompts import SYSTEM_PROMPT


def _build_messages(history: Iterable[Message], system_prompt: str) -> list[dict[str, str]]:
    messages = [{"role": "system", "content": system_prompt}]
    for item in history:
        messages.append({"role": item.role, "content": item.content})
    return messages


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
    if text:
        return text
    return "យាយសូមអភ័យទោស កូនអើយ។ យាយមិនទាន់អាចឆ្លើយបានច្បាស់ទេ សូមសួរម្តងទៀត។"
