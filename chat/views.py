import csv
import json
from datetime import timedelta

from django.conf import settings
from django.contrib import messages
from django.contrib.auth import logout
from django.contrib.auth.decorators import login_required
from django.contrib.auth.views import LoginView
from django.core.cache import cache
from django.db import models
from django.core.paginator import Paginator
from django.http import HttpRequest, HttpResponse, HttpResponseForbidden, JsonResponse
from django.shortcuts import get_object_or_404
from django.shortcuts import redirect, render
from django.urls import reverse_lazy
from django.utils import timezone
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods

from .forms import (
    AssistantAdvancedSettingsForm,
    AssistantEngineSettingsForm,
    AssistantPromptForm,
    OperatorAuthenticationForm,
)
from .models import AssistantConfig, AssistantConfigHistory, Conversation, Message
from .services import analyze_image_bytes, get_yeay_monny_reply, transcribe_audio_bytes
from .telegram import fetch_telegram_file, send_telegram_message

FIRST_MESSAGE = "យាយមុន្នីនៅទីនេះ ចៅអើយ។ សរសេរមកយាយបាន។ ប្រាប់យាយពីឈ្មោះ ថ្ងៃកំណើត បើចាំបាន ហើយប្រាប់ថាចង់អោយយាយមើលរឿងអ្វី។"
TEXT_PREFERRED_NOTE = (
    "ចៅអើយ យាយស្តាប់សម្លេងមិនទាន់ច្បាស់ទេ។ "
    "សូមសរសេរជាអក្សរមកយាយម្ដងទៀត។ "
    "អក្សរងាយឱ្យយាយមើលបានច្បាស់ជាងសម្លេង។"
)
ENGINE_CHECKLIST = [
    ("Feng Shui (WOFS-style)", "enable_fengshui_engine", "WOFS tools style (Kua, Flying Star, Tai Sui)"),
    ("Face Reading", "enable_face_reading_engine", "Lok Tin face-reading structure"),
    ("Palm Reading", "enable_palm_reading_engine", "Allure hand-line framework"),
    ("Vehicle Numerology", "enable_vehicle_numerology_engine", "Nehaa-style root-number approach"),
    ("House Numerology", "enable_house_numerology_engine", "Arviend Sud moving-number method"),
    ("Love Compatibility", "enable_compatibility_engine", "Astromix-style compatibility flow"),
    ("Financial Advisory", "enable_financial_advisory_engine", "Goal-plan + risk-aware advisory"),
]


def _is_valid_upload_size(file_obj, max_mb: int) -> bool:
    return bool(file_obj and file_obj.size <= max_mb * 1024 * 1024)


def _rate_limit_hit(*, key: str, max_requests: int, window_seconds: int) -> bool:
    if max_requests <= 0 or window_seconds <= 0:
        return False
    window = max(1, window_seconds)
    if cache.add(key, 1, timeout=window):
        return False
    try:
        current = cache.incr(key)
    except ValueError:
        cache.set(key, 1, timeout=window)
        current = 1
    return int(current) > max_requests


def _build_multimodal_user_content(
    *,
    user_text: str,
    audio_transcript: str,
    image_summary: str,
) -> str:
    blocks: list[str] = []
    if user_text:
        blocks.append(f"សំណួររបស់អ្នកប្រើ៖ {user_text}")
    if audio_transcript:
        blocks.append(f"អត្ថបទបានបម្លែងពីសម្លេង៖ {audio_transcript}")
    if image_summary:
        blocks.append(f"ការពិពណ៌នារូបភាពសម្រាប់មើលជោគជាតា៖ {image_summary}")
    content = "\n\n".join(blocks).strip()
    if len(content) > settings.MAX_USER_MESSAGE_CHARS:
        return content[: settings.MAX_USER_MESSAGE_CHARS]
    return content


def _build_telegram_multimodal_user_content(
    *,
    text: str,
    caption: str,
    audio_transcript: str,
    image_summary: str,
    has_voice: bool,
    has_image: bool,
) -> str:
    blocks: list[str] = []
    base_text = text or caption
    if base_text:
        blocks.append(f"សំណួររបស់អ្នកប្រើ៖ {base_text}")

    if audio_transcript:
        blocks.append(f"អត្ថបទបានបម្លែងពីសម្លេង៖ {audio_transcript}")
    elif has_voice:
        blocks.append("អ្នកប្រើបានផ្ញើសម្លេង ប៉ុន្តែប្រព័ន្ធស្តាប់មិនទាន់ច្បាស់។")

    if image_summary:
        blocks.append(f"ការពិពណ៌នារូបភាពសម្រាប់មើលជោគជាតា៖ {image_summary}")
    elif has_image:
        blocks.append("អ្នកប្រើបានផ្ញើរូបភាព ប៉ុន្តែប្រព័ន្ធមើលមិនទាន់ច្បាស់។")

    content = "\n\n".join(blocks).strip()
    if len(content) > settings.MAX_USER_MESSAGE_CHARS:
        return content[: settings.MAX_USER_MESSAGE_CHARS]
    return content


def _conversation_profile(conversation: Conversation) -> dict[str, str]:
    return {
        "name": (conversation.name or "").strip(),
        "birth_info": (conversation.birth_info or "").strip(),
        "question_focus": (conversation.question_focus or "").strip(),
    }


class OperatorLoginView(LoginView):
    template_name = "chat/operator_login.html"
    redirect_authenticated_user = True
    next_page = reverse_lazy("chat:operator_dashboard")
    authentication_form = OperatorAuthenticationForm

    def _bucket_key(self, username: str) -> str:
        ip = (self.request.META.get("REMOTE_ADDR") or "").strip() or "unknown"
        normalized = (username or "").strip().lower() or "unknown"
        return f"operator_login_fail:{ip}:{normalized}"

    def dispatch(self, request, *args, **kwargs):
        if request.method == "POST":
            raw_username = (request.POST.get("username") or "").strip()
            key = self._bucket_key(raw_username)
            fail_count = int(cache.get(key, 0) or 0)
            if fail_count >= settings.OPERATOR_LOGIN_MAX_ATTEMPTS:
                form = self.get_form()
                form.add_error(
                    None,
                    "សុំព្យាយាមច្រើនពេក។ សូមរង់ចាំបន្តិចហើយសាកម្តងទៀត។",
                )
                return self.render_to_response(self.get_context_data(form=form), status=429)
        return super().dispatch(request, *args, **kwargs)

    def form_valid(self, form):
        response = super().form_valid(form)
        raw_username = (self.request.POST.get("username") or "").strip()
        cache.delete(self._bucket_key(raw_username))
        user = self.request.user
        if not _has_operator_view_permission(user):
            logout(self.request)
            messages.error(
                self.request,
                "គណនីនេះមិនទាន់មានសិទ្ធិប្រើផ្ទាំងប្រតិបត្តិការទេ។ សូមទាក់ទងអ្នកគ្រប់គ្រង។",
            )
            return redirect("chat:operator_login")
        return response

    def form_invalid(self, form):
        raw_username = (self.request.POST.get("username") or "").strip()
        key = self._bucket_key(raw_username)
        window = max(60, settings.OPERATOR_LOGIN_WINDOW_SECONDS)
        if cache.add(key, 1, timeout=window) is False:
            try:
                cache.incr(key)
            except ValueError:
                cache.set(key, 1, timeout=window)
        return super().form_invalid(form)


@require_http_methods(["POST"])
def operator_logout(request: HttpRequest) -> HttpResponse:
    logout(request)
    return redirect("chat:operator_login")


def _operator_forbidden(request: HttpRequest) -> HttpResponse:
    return render(request, "chat/operator_forbidden.html", status=403)


def _get_or_create_conversation(request: HttpRequest) -> Conversation:
    if not request.session.session_key:
        request.session.create()

    session_key = request.session.session_key
    conversation_id = request.session.get("conversation_id")

    if conversation_id:
        conversation = Conversation.objects.filter(id=conversation_id).first()
        if conversation:
            return conversation

    conversation = Conversation.objects.create(session_key=session_key)
    request.session["conversation_id"] = str(conversation.id)
    return conversation


def _get_or_create_telegram_conversation(chat_id: int | str) -> Conversation:
    session_key = f"tg_{chat_id}"
    conversation = Conversation.objects.filter(session_key=session_key).first()
    if conversation:
        return conversation
    return Conversation.objects.create(session_key=session_key)


def _has_operator_view_permission(user) -> bool:
    return bool(user and user.is_authenticated and user.has_perm("chat.view_assistantconfig"))


def _can_edit_prompt(user) -> bool:
    return bool(user and user.is_authenticated and user.has_perm("chat.change_assistantconfig"))


def _can_manage_advanced_settings(user) -> bool:
    return bool(user and user.is_authenticated and user.has_perm("chat.manage_advanced_assistantconfig"))


def _can_rollback(user) -> bool:
    return bool(user and user.is_authenticated and user.has_perm("chat.rollback_assistantconfig"))


def _build_dashboard_context(request: HttpRequest, *, config: AssistantConfig) -> dict:
    history_qs = config.history.all()
    history_entries = Paginator(history_qs, 10).get_page(request.GET.get("history_page"))

    query = (request.GET.get("q") or "").strip()
    conversations_qs = Conversation.objects.all()
    if query:
        conversations_qs = conversations_qs.filter(
            models.Q(session_key__icontains=query)
            | models.Q(name__icontains=query)
            | models.Q(question_focus__icontains=query)
        )

    recent_conversations = Paginator(
        conversations_qs.order_by("-updated_at"),
        20,
    ).get_page(request.GET.get("conversation_page"))
    recent_messages = Paginator(
        Message.objects.select_related("conversation").order_by("-created_at"),
        20,
    ).get_page(request.GET.get("message_page"))
    users_page = Paginator(
        conversations_qs.annotate(
            messages_count=models.Count("messages"),
            user_messages_count=models.Count("messages", filter=models.Q(messages__role=Message.Role.USER)),
            assistant_messages_count=models.Count("messages", filter=models.Q(messages__role=Message.Role.ASSISTANT)),
            last_message_at=models.Max("messages__created_at"),
        ).order_by("-updated_at"),
        30,
    ).get_page(request.GET.get("users_page"))
    since_24h = timezone.now() - timedelta(hours=24)
    contacts_qs = Conversation.objects.filter(marketing_opt_in=True).exclude(
        contact_email="",
        contact_phone="",
        telegram_username="",
    )
    recent_contacts = contacts_qs.order_by("-updated_at")[:30]
    engine_checklist = [
        {
            "name": name,
            "enabled": bool(getattr(config, field_name)),
            "source": source,
        }
        for name, field_name, source in ENGINE_CHECKLIST
    ]

    return {
        "history_entries": history_entries,
        "query": query,
        "recent_conversations": recent_conversations,
        "recent_messages": recent_messages,
        "users_page": users_page,
        "total_conversations": Conversation.objects.count(),
        "total_messages": Message.objects.count(),
        "messages_24h": Message.objects.filter(created_at__gte=since_24h).count(),
        "openai_ready": bool(settings.OPENAI_API_KEY),
        "telegram_ready": bool(settings.TELEGRAM_BOT_TOKEN),
        "telegram_webhook_path": settings.TELEGRAM_WEBHOOK_PATH,
        "opted_in_contacts": contacts_qs.count(),
        "recent_contacts": recent_contacts,
        "engine_checklist": engine_checklist,
    }


@require_http_methods(["GET", "POST", "HEAD"])
def chat_home(request: HttpRequest) -> HttpResponse:
    conversation = _get_or_create_conversation(request)

    if request.method == "POST":
        user_text = (request.POST.get("message") or "").strip()
        image_file = request.FILES.get("image")
        voice_file = request.FILES.get("voice")

        audio_transcript = ""
        image_summary = ""
        has_payload = bool(user_text or image_file or voice_file)
        if has_payload:
            rate_key = f"chat_post:{request.session.session_key}:{request.META.get('REMOTE_ADDR', 'unknown')}"
            if _rate_limit_hit(
                key=rate_key,
                max_requests=settings.CHAT_RATE_LIMIT_MAX_REQUESTS,
                window_seconds=settings.CHAT_RATE_LIMIT_WINDOW_SECONDS,
            ):
                messages.error(request, "សំណើច្រើនពេក។ សូមរង់ចាំបន្តិចហើយសាកម្តងទៀត។")
                return redirect("chat:home")
            name = (request.POST.get("name") or "").strip()
            birth_info = (request.POST.get("birth_info") or "").strip()
            question_focus = (request.POST.get("question_focus") or "").strip()
            contact_email = (request.POST.get("contact_email") or "").strip()
            contact_phone = (request.POST.get("contact_phone") or "").strip()
            marketing_opt_in = request.POST.get("marketing_opt_in") == "on"

            if name:
                conversation.name = name
            if birth_info:
                conversation.birth_info = birth_info
            if question_focus:
                conversation.question_focus = question_focus
            if contact_email:
                conversation.contact_email = contact_email
            if contact_phone:
                conversation.contact_phone = contact_phone
            conversation.apply_marketing_opt_in(marketing_opt_in)
            conversation.save(
                update_fields=[
                    "name",
                    "birth_info",
                    "question_focus",
                    "contact_email",
                    "contact_phone",
                    "marketing_opt_in",
                    "marketing_opt_in_at",
                    "updated_at",
                ]
            )

            if voice_file:
                if _is_valid_upload_size(voice_file, settings.MAX_AUDIO_UPLOAD_MB):
                    audio_transcript = transcribe_audio_bytes(
                        filename=voice_file.name,
                        audio_bytes=voice_file.read(),
                    )
                    if not audio_transcript and not user_text:
                        messages.error(request, TEXT_PREFERRED_NOTE)
                        return redirect("chat:home")
                else:
                    messages.error(request, "ឯកសារសម្លេងធំពេក។ សូមបញ្ចូលឯកសារតូចជាងកំណត់។")

            if image_file:
                if _is_valid_upload_size(image_file, settings.MAX_IMAGE_UPLOAD_MB):
                    image_summary = analyze_image_bytes(
                        filename=image_file.name,
                        content_type=image_file.content_type or "image/jpeg",
                        image_bytes=image_file.read(),
                        user_text=user_text,
                    )
                else:
                    messages.error(request, "រូបភាពធំពេក។ សូមបញ្ចូលរូបតូចជាងកំណត់។")

            combined_user_content = _build_multimodal_user_content(
                user_text=user_text,
                audio_transcript=audio_transcript,
                image_summary=image_summary,
            )
            if not combined_user_content:
                combined_user_content = "ចៅអើយ យាយបានទទួលឯកសារ ប៉ុន្តែមិនទាន់អាចអានបានច្បាស់។"

            Message.objects.create(
                conversation=conversation,
                role=Message.Role.USER,
                content=combined_user_content,
            )

            history = conversation.messages.all()
            assistant_text = get_yeay_monny_reply(history, user_profile=_conversation_profile(conversation))

            Message.objects.create(
                conversation=conversation,
                role=Message.Role.ASSISTANT,
                content=assistant_text,
            )

        return redirect("chat:home")

    chat_messages = list(conversation.messages.all())
    if not chat_messages:
        chat_messages = [
            Message(
                role=Message.Role.ASSISTANT,
                content=FIRST_MESSAGE,
            )
        ]

    return render(
        request,
        "chat/home.html",
        {
            "conversation": conversation,
            "chat_messages": chat_messages,
        },
    )


@login_required(login_url="chat:operator_login")
@require_http_methods(["GET", "POST"])
def operator_dashboard(request: HttpRequest) -> HttpResponse:
    if not _has_operator_view_permission(request.user):
        return _operator_forbidden(request)

    config = AssistantConfig.get_solo()
    can_edit_prompt = _can_edit_prompt(request.user)
    can_manage_advanced = _can_manage_advanced_settings(request.user)
    can_rollback = _can_rollback(request.user)

    if request.method == "POST":
        action = request.POST.get("action")

        if action == "save_prompt":
            if not can_edit_prompt:
                return _operator_forbidden(request)
            form = AssistantPromptForm(request.POST, instance=config)
            advanced_form = AssistantAdvancedSettingsForm(instance=config)
            engine_form = AssistantEngineSettingsForm(instance=config)
            if form.is_valid():
                AssistantConfigHistory.snapshot(
                    config=config,
                    changed_by=request.user.get_username(),
                    change_reason=AssistantConfigHistory.ChangeReason.UPDATE,
                )
                updated_config = form.save(commit=False)
                updated_config.updated_by = request.user.get_username()
                updated_config.save()
                messages.success(request, "បានរក្សាទុកសារណែនាំរួចរាល់។")
                return redirect("chat:operator_dashboard")
        elif action == "save_advanced":
            if not can_manage_advanced:
                return _operator_forbidden(request)
            form = AssistantPromptForm(instance=config)
            advanced_form = AssistantAdvancedSettingsForm(request.POST, instance=config)
            engine_form = AssistantEngineSettingsForm(instance=config)
            if advanced_form.is_valid():
                AssistantConfigHistory.snapshot(
                    config=config,
                    changed_by=request.user.get_username(),
                    change_reason=AssistantConfigHistory.ChangeReason.UPDATE,
                )
                updated_config = advanced_form.save(commit=False)
                updated_config.updated_by = request.user.get_username()
                updated_config.save()
                messages.success(request, "បានរក្សាទុកការកំណត់ម៉ូឌែលរួចរាល់។")
                return redirect("chat:operator_dashboard")
        elif action == "save_engines":
            if not can_manage_advanced:
                return _operator_forbidden(request)
            form = AssistantPromptForm(instance=config)
            advanced_form = AssistantAdvancedSettingsForm(instance=config)
            engine_form = AssistantEngineSettingsForm(request.POST, instance=config)
            if engine_form.is_valid():
                AssistantConfigHistory.snapshot(
                    config=config,
                    changed_by=request.user.get_username(),
                    change_reason=AssistantConfigHistory.ChangeReason.UPDATE,
                )
                updated_config = engine_form.save(commit=False)
                updated_config.updated_by = request.user.get_username()
                updated_config.save()
                messages.success(request, "បានរក្សាទុកការកំណត់ម៉ាស៊ីនទាយរួចរាល់។")
                return redirect("chat:operator_dashboard")
        elif action == "rollback":
            if not can_rollback:
                return _operator_forbidden(request)
            version_id = request.POST.get("version_id")
            history_item = get_object_or_404(
                AssistantConfigHistory.objects.filter(config=config),
                pk=version_id,
            )
            AssistantConfigHistory.snapshot(
                config=config,
                changed_by=request.user.get_username(),
                change_reason=AssistantConfigHistory.ChangeReason.ROLLBACK,
            )
            config.system_prompt = history_item.system_prompt
            config.model_name = history_item.model_name
            config.temperature = history_item.temperature
            config.enable_fengshui_engine = history_item.enable_fengshui_engine
            config.enable_face_reading_engine = history_item.enable_face_reading_engine
            config.enable_palm_reading_engine = history_item.enable_palm_reading_engine
            config.enable_vehicle_numerology_engine = history_item.enable_vehicle_numerology_engine
            config.enable_house_numerology_engine = history_item.enable_house_numerology_engine
            config.enable_compatibility_engine = history_item.enable_compatibility_engine
            config.enable_financial_advisory_engine = history_item.enable_financial_advisory_engine
            config.compatibility_score_threshold = history_item.compatibility_score_threshold
            config.engine_operator_note = history_item.engine_operator_note
            config.updated_by = request.user.get_username()
            config.save()
            messages.success(request, "បានត្រឡប់ទៅកំណែមុនរួចរាល់។")
            return redirect("chat:operator_dashboard")
        else:
            form = AssistantPromptForm(instance=config)
            advanced_form = AssistantAdvancedSettingsForm(instance=config)
            engine_form = AssistantEngineSettingsForm(instance=config)
    else:
        form = AssistantPromptForm(instance=config)
        advanced_form = AssistantAdvancedSettingsForm(instance=config)
        engine_form = AssistantEngineSettingsForm(instance=config)

    context = _build_dashboard_context(request, config=config)
    context.update(
        {
            "form": form,
            "advanced_form": advanced_form,
            "engine_form": engine_form,
            "can_edit_prompt": can_edit_prompt,
            "can_manage_advanced": can_manage_advanced,
            "can_rollback": can_rollback,
        }
    )
    return render(request, "chat/operator_dashboard.html", context)


@login_required(login_url="chat:operator_login")
@require_http_methods(["GET"])
def operator_conversation_detail(request: HttpRequest, conversation_id) -> HttpResponse:
    if not _has_operator_view_permission(request.user):
        return _operator_forbidden(request)
    conversation = get_object_or_404(Conversation, pk=conversation_id)
    messages_page = Paginator(
        conversation.messages.all(),
        50,
    ).get_page(request.GET.get("page"))
    return render(
        request,
        "chat/operator_conversation_detail.html",
        {
            "conversation": conversation,
            "messages_page": messages_page,
        },
    )


@csrf_exempt
@require_http_methods(["POST"])
def telegram_webhook(request: HttpRequest) -> JsonResponse | HttpResponseForbidden:
    if not settings.TELEGRAM_BOT_TOKEN:
        return JsonResponse({"ok": False, "error": "telegram bot token is not configured"}, status=503)

    if not settings.DEBUG and not settings.TELEGRAM_WEBHOOK_SECRET:
        return JsonResponse({"ok": False, "error": "telegram webhook secret is required in production"}, status=503)

    if settings.TELEGRAM_WEBHOOK_SECRET:
        given_secret = request.headers.get("X-Telegram-Bot-Api-Secret-Token", "")
        if given_secret != settings.TELEGRAM_WEBHOOK_SECRET:
            return HttpResponseForbidden("Invalid Telegram webhook secret")

    if len(request.body) > settings.DATA_UPLOAD_MAX_MEMORY_SIZE:
        return JsonResponse({"ok": False, "error": "payload too large"}, status=413)

    try:
        update = json.loads(request.body.decode("utf-8"))
    except json.JSONDecodeError:
        return JsonResponse({"ok": False, "error": "invalid json"}, status=400)

    message = update.get("message") or update.get("edited_message")
    if not message:
        return JsonResponse({"ok": True})

    chat = message.get("chat") or {}
    from_user = message.get("from") or {}
    chat_id = chat.get("id")
    text = (message.get("text") or "").strip()
    caption = (message.get("caption") or "").strip()
    voice_info = message.get("voice")
    audio_info = message.get("audio")
    video_note_info = message.get("video_note")
    document_info = message.get("document") or {}
    photo_list = message.get("photo") or []

    if not chat_id:
        return JsonResponse({"ok": True})

    if _rate_limit_hit(
        key=f"tg_msg:{chat_id}",
        max_requests=settings.TELEGRAM_RATE_LIMIT_MAX_REQUESTS,
        window_seconds=settings.TELEGRAM_RATE_LIMIT_WINDOW_SECONDS,
    ):
        send_telegram_message(chat_id, "ចៅអើយ សំណើច្រើនពេក។ សូមរង់ចាំបន្តិចហើយសាកម្តងទៀត។")
        return JsonResponse({"ok": True})

    audio_transcript = ""
    image_summary = ""
    has_voice = bool(voice_info or audio_info or video_note_info)
    has_image = bool(photo_list)

    if voice_info and voice_info.get("file_id"):
        fetched = fetch_telegram_file(
            voice_info["file_id"],
            max_bytes=settings.MAX_AUDIO_UPLOAD_MB * 1024 * 1024,
        )
        if fetched:
            content, _content_type, filename = fetched
            audio_transcript = transcribe_audio_bytes(filename=filename, audio_bytes=content)
    elif audio_info and audio_info.get("file_id"):
        fetched = fetch_telegram_file(
            audio_info["file_id"],
            max_bytes=settings.MAX_AUDIO_UPLOAD_MB * 1024 * 1024,
        )
        if fetched:
            content, _content_type, filename = fetched
            audio_transcript = transcribe_audio_bytes(filename=filename, audio_bytes=content)
    elif video_note_info and video_note_info.get("file_id"):
        fetched = fetch_telegram_file(
            video_note_info["file_id"],
            max_bytes=settings.MAX_AUDIO_UPLOAD_MB * 1024 * 1024,
        )
        if fetched:
            content, _content_type, filename = fetched
            audio_transcript = transcribe_audio_bytes(filename=filename, audio_bytes=content)

    if photo_list:
        best_photo = photo_list[-1]
        if best_photo.get("file_id"):
            fetched = fetch_telegram_file(
                best_photo["file_id"],
                max_bytes=settings.MAX_IMAGE_UPLOAD_MB * 1024 * 1024,
            )
            if fetched:
                content, content_type, filename = fetched
                image_summary = analyze_image_bytes(
                    filename=filename,
                    content_type=content_type,
                    image_bytes=content,
                    user_text=text or caption,
                )
    elif document_info.get("file_id") and str(document_info.get("mime_type", "")).startswith("image/"):
        has_image = True
        fetched = fetch_telegram_file(
            document_info["file_id"],
            max_bytes=settings.MAX_IMAGE_UPLOAD_MB * 1024 * 1024,
        )
        if fetched:
            content, content_type, filename = fetched
            image_summary = analyze_image_bytes(
                filename=filename,
                content_type=content_type,
                image_bytes=content,
                user_text=text or caption,
            )

    combined_user_content = _build_telegram_multimodal_user_content(
        text=text,
        caption=caption,
        audio_transcript=audio_transcript,
        image_summary=image_summary,
        has_voice=has_voice,
        has_image=has_image,
    )

    if has_voice and not audio_transcript and not (text or caption):
        send_telegram_message(chat_id, TEXT_PREFERRED_NOTE)
        return JsonResponse({"ok": True})

    if not combined_user_content:
        send_telegram_message(chat_id, "ចៅអើយ សូមផ្ញើសារជាអក្សរ សម្លេង ឬរូបភាពមកយាយ។")
        return JsonResponse({"ok": True})

    conversation = _get_or_create_telegram_conversation(chat_id)
    if not conversation.name:
        full_name = " ".join(
            p
            for p in [
                (from_user.get("first_name") or "").strip(),
                (from_user.get("last_name") or "").strip(),
            ]
            if p
        ).strip()
        if full_name:
            conversation.name = full_name
            conversation.save(update_fields=["name", "updated_at"])
    username = (from_user.get("username") or "").strip()
    if username and not conversation.telegram_username:
        conversation.telegram_username = f"@{username}"
        conversation.save(update_fields=["telegram_username", "updated_at"])

    Message.objects.create(
        conversation=conversation,
        role=Message.Role.USER,
        content=combined_user_content,
    )

    history = conversation.messages.all()
    assistant_text = get_yeay_monny_reply(history, user_profile=_conversation_profile(conversation))

    Message.objects.create(
        conversation=conversation,
        role=Message.Role.ASSISTANT,
        content=assistant_text,
    )
    send_telegram_message(chat_id, assistant_text)

    return JsonResponse({"ok": True})


@login_required(login_url="chat:operator_login")
@require_http_methods(["GET"])
def operator_export_contacts_csv(request: HttpRequest) -> HttpResponse:
    if not _can_manage_advanced_settings(request.user):
        return _operator_forbidden(request)

    rows = (
        Conversation.objects.filter(marketing_opt_in=True)
        .exclude(contact_email="", contact_phone="", telegram_username="")
        .order_by("-updated_at")
    )
    response = HttpResponse(content_type="text/csv; charset=utf-8")
    response["Content-Disposition"] = 'attachment; filename="yeaymonny_contacts.csv"'

    writer = csv.writer(response)
    writer.writerow(
        [
            "session_key",
            "name",
            "birth_info",
            "question_focus",
            "contact_email",
            "contact_phone",
            "telegram_username",
            "marketing_opt_in",
            "marketing_opt_in_at",
            "updated_at",
        ]
    )
    for convo in rows:
        writer.writerow(
            [
                convo.session_key,
                convo.name,
                convo.birth_info,
                convo.question_focus,
                convo.contact_email,
                convo.contact_phone,
                convo.telegram_username,
                "yes" if convo.marketing_opt_in else "no",
                convo.marketing_opt_in_at.isoformat() if convo.marketing_opt_in_at else "",
                convo.updated_at.isoformat(),
            ]
        )
    return response


@login_required(login_url="chat:operator_login")
@require_http_methods(["GET"])
def operator_export_users_csv(request: HttpRequest) -> HttpResponse:
    if not _can_manage_advanced_settings(request.user):
        return _operator_forbidden(request)

    query = (request.GET.get("q") or "").strip()
    users_qs = Conversation.objects.all()
    if query:
        users_qs = users_qs.filter(
            models.Q(session_key__icontains=query)
            | models.Q(name__icontains=query)
            | models.Q(contact_email__icontains=query)
            | models.Q(contact_phone__icontains=query)
            | models.Q(telegram_username__icontains=query)
            | models.Q(question_focus__icontains=query)
        )
    users_qs = users_qs.annotate(
        messages_count=models.Count("messages"),
        user_messages_count=models.Count("messages", filter=models.Q(messages__role=Message.Role.USER)),
        assistant_messages_count=models.Count("messages", filter=models.Q(messages__role=Message.Role.ASSISTANT)),
        last_message_at=models.Max("messages__created_at"),
    ).order_by("-updated_at")

    response = HttpResponse(content_type="text/csv; charset=utf-8")
    response["Content-Disposition"] = 'attachment; filename="yeaymonny_users.csv"'

    writer = csv.writer(response)
    writer.writerow(
        [
            "session_key",
            "channel",
            "name",
            "birth_info",
            "question_focus",
            "contact_email",
            "contact_phone",
            "telegram_username",
            "marketing_opt_in",
            "messages_count",
            "user_messages_count",
            "assistant_messages_count",
            "last_message_at",
            "created_at",
            "updated_at",
        ]
    )
    for user in users_qs:
        channel = "telegram" if str(user.session_key).startswith("tg_") else "web"
        writer.writerow(
            [
                user.session_key,
                channel,
                user.name,
                user.birth_info,
                user.question_focus,
                user.contact_email,
                user.contact_phone,
                user.telegram_username,
                "yes" if user.marketing_opt_in else "no",
                user.messages_count or 0,
                user.user_messages_count or 0,
                user.assistant_messages_count or 0,
                user.last_message_at.isoformat() if user.last_message_at else "",
                user.created_at.isoformat(),
                user.updated_at.isoformat(),
            ]
        )
    return response
