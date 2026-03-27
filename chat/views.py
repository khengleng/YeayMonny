from django.http import HttpRequest, HttpResponse
from django.shortcuts import redirect, render
from django.views.decorators.http import require_http_methods

from .models import Conversation, Message
from .services import get_yeay_monny_reply

FIRST_MESSAGE = "យាយមុន្នីនៅទីនេះ កូនអើយ។ មកអង្គុយសិន។ ប្រាប់យាយពីឈ្មោះ ថ្ងៃកំណើត បើចាំបាន ហើយប្រាប់ថាចង់អោយយាយមើលរឿងអ្វី។"


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
