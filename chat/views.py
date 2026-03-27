import json

from django.conf import settings
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.contrib.auth.views import LoginView, LogoutView
from django.http import HttpRequest, HttpResponse, HttpResponseForbidden, JsonResponse
from django.shortcuts import redirect, render
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods

from .forms import AssistantConfigForm
from .models import AssistantConfig, Conversation, Message
from .services import get_yeay_monny_reply
from .telegram import send_telegram_message

FIRST_MESSAGE = "យាយមុន្នីនៅទីនេះ កូនអើយ។ មកអង្គុយសិន។ ប្រាប់យាយពីឈ្មោះ ថ្ងៃកំណើត បើចាំបាន ហើយប្រាប់ថាចង់អោយយាយមើលរឿងអ្វី។"


class OperatorLoginView(LoginView):
    template_name = "chat/operator_login.html"
    redirect_authenticated_user = True


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


def _is_staff_user(user) -> bool:
    return bool(user and user.is_authenticated and user.is_staff)


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
    if not _is_staff_user(request.user):
        return HttpResponse(status=403)

    config = AssistantConfig.get_solo()

    if request.method == "POST":
        form = AssistantConfigForm(request.POST, instance=config)
        if form.is_valid():
            updated_config = form.save(commit=False)
            updated_config.updated_by = request.user.get_username()
            updated_config.save()
            messages.success(request, "Updated configuration successfully.")
            return redirect("chat:operator_dashboard")
    else:
        form = AssistantConfigForm(instance=config)

    return render(request, "chat/operator_dashboard.html", {"form": form})


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
