import json

from django.conf import settings
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.contrib.auth.views import LoginView, LogoutView
from django.http import HttpRequest, HttpResponse, HttpResponseForbidden, JsonResponse
from django.shortcuts import get_object_or_404
from django.shortcuts import redirect, render
from django.urls import reverse_lazy
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods

from .forms import AssistantAdvancedSettingsForm, AssistantPromptForm
from .models import AssistantConfig, AssistantConfigHistory, Conversation, Message
from .services import get_yeay_monny_reply
from .telegram import send_telegram_message

FIRST_MESSAGE = "យាយមុន្នីនៅទីនេះ កូនអើយ។ មកអង្គុយសិន។ ប្រាប់យាយពីឈ្មោះ ថ្ងៃកំណើត បើចាំបាន ហើយប្រាប់ថាចង់អោយយាយមើលរឿងអ្វី។"


class OperatorLoginView(LoginView):
    template_name = "chat/operator_login.html"
    redirect_authenticated_user = True
    next_page = reverse_lazy("chat:operator_dashboard")


class OperatorLogoutView(LogoutView):
    next_page = "chat:operator_login"


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


@require_http_methods(["GET", "POST"])
def chat_home(request: HttpRequest) -> HttpResponse:
    conversation = _get_or_create_conversation(request)

    if request.method == "POST":
        user_text = (request.POST.get("message") or "").strip()
        if user_text:
            name = (request.POST.get("name") or "").strip()
            birth_info = (request.POST.get("birth_info") or "").strip()
            question_focus = (request.POST.get("question_focus") or "").strip()

            if name:
                conversation.name = name
            if birth_info:
                conversation.birth_info = birth_info
            if question_focus:
                conversation.question_focus = question_focus
            conversation.save(update_fields=["name", "birth_info", "question_focus", "updated_at"])

            Message.objects.create(
                conversation=conversation,
                role=Message.Role.USER,
                content=user_text,
            )

            history = conversation.messages.all()
            assistant_text = get_yeay_monny_reply(history)

            Message.objects.create(
                conversation=conversation,
                role=Message.Role.ASSISTANT,
                content=assistant_text,
            )

        return redirect("chat:home")

    messages = list(conversation.messages.all())
    if not messages:
        messages = [
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
            "messages": messages,
        },
    )


@login_required(login_url="chat:operator_login")
@require_http_methods(["GET", "POST"])
def operator_dashboard(request: HttpRequest) -> HttpResponse:
    if not _has_operator_view_permission(request.user):
        return HttpResponse(status=403)

    config = AssistantConfig.get_solo()
    can_edit_prompt = _can_edit_prompt(request.user)
    can_manage_advanced = _can_manage_advanced_settings(request.user)
    can_rollback = _can_rollback(request.user)

    if request.method == "POST":
        action = request.POST.get("action")

        if action == "save_prompt":
            if not can_edit_prompt:
                return HttpResponse(status=403)
            form = AssistantPromptForm(request.POST, instance=config)
            advanced_form = AssistantAdvancedSettingsForm(instance=config)
            if form.is_valid():
                AssistantConfigHistory.snapshot(
                    config=config,
                    changed_by=request.user.get_username(),
                    change_reason=AssistantConfigHistory.ChangeReason.UPDATE,
                )
                updated_config = form.save(commit=False)
                updated_config.updated_by = request.user.get_username()
                updated_config.save()
                messages.success(request, "បានរក្សាទុក Prompt រួចរាល់។")
                return redirect("chat:operator_dashboard")
        elif action == "save_advanced":
            if not can_manage_advanced:
                return HttpResponse(status=403)
            form = AssistantPromptForm(instance=config)
            advanced_form = AssistantAdvancedSettingsForm(request.POST, instance=config)
            if advanced_form.is_valid():
                AssistantConfigHistory.snapshot(
                    config=config,
                    changed_by=request.user.get_username(),
                    change_reason=AssistantConfigHistory.ChangeReason.UPDATE,
                )
                updated_config = advanced_form.save(commit=False)
                updated_config.updated_by = request.user.get_username()
                updated_config.save()
                messages.success(request, "បានរក្សាទុក Model/Temperature រួចរាល់។")
                return redirect("chat:operator_dashboard")
        elif action == "rollback":
            if not can_rollback:
                return HttpResponse(status=403)
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
            config.updated_by = request.user.get_username()
            config.save()
            messages.success(request, "បាន Rollback ទៅកំណែដែលជ្រើសរើសរួចរាល់។")
            return redirect("chat:operator_dashboard")
        else:
            form = AssistantPromptForm(instance=config)
            advanced_form = AssistantAdvancedSettingsForm(instance=config)
    else:
        form = AssistantPromptForm(instance=config)
        advanced_form = AssistantAdvancedSettingsForm(instance=config)

    history_entries = config.history.all()[:15]
    return render(
        request,
        "chat/operator_dashboard.html",
        {
            "form": form,
            "advanced_form": advanced_form,
            "history_entries": history_entries,
            "can_edit_prompt": can_edit_prompt,
            "can_manage_advanced": can_manage_advanced,
            "can_rollback": can_rollback,
        },
    )


@csrf_exempt
@require_http_methods(["POST"])
def telegram_webhook(request: HttpRequest) -> JsonResponse | HttpResponseForbidden:
    if not settings.TELEGRAM_BOT_TOKEN:
        return JsonResponse({"ok": False, "error": "telegram bot token is not configured"}, status=503)

    if settings.TELEGRAM_WEBHOOK_SECRET:
        given_secret = request.headers.get("X-Telegram-Bot-Api-Secret-Token", "")
        if given_secret != settings.TELEGRAM_WEBHOOK_SECRET:
            return HttpResponseForbidden("Invalid Telegram webhook secret")

    try:
        update = json.loads(request.body.decode("utf-8"))
    except json.JSONDecodeError:
        return JsonResponse({"ok": False, "error": "invalid json"}, status=400)

    message = update.get("message") or update.get("edited_message")
    if not message:
        return JsonResponse({"ok": True})

    chat = message.get("chat") or {}
    chat_id = chat.get("id")
    text = (message.get("text") or "").strip()

    if not chat_id:
        return JsonResponse({"ok": True})

    if not text:
        send_telegram_message(chat_id, "កូនអើយ សូមផ្ញើសារជាអក្សរមកយាយ។")
        return JsonResponse({"ok": True})

    conversation = _get_or_create_telegram_conversation(chat_id)
    Message.objects.create(
        conversation=conversation,
        role=Message.Role.USER,
        content=text,
    )

    history = conversation.messages.all()
    assistant_text = get_yeay_monny_reply(history)

    Message.objects.create(
        conversation=conversation,
        role=Message.Role.ASSISTANT,
        content=assistant_text,
    )
    send_telegram_message(chat_id, assistant_text)

    return JsonResponse({"ok": True})
