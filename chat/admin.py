from django.contrib import admin

from .models import Conversation, Message


class MessageInline(admin.TabularInline):
    model = Message
    extra = 0
    readonly_fields = ("role", "content", "created_at")
    can_delete = False


@admin.register(Conversation)
class ConversationAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "session_key",
        "name",
        "question_focus",
        "created_at",
        "updated_at",
    )
    search_fields = ("id", "session_key", "name", "birth_info", "question_focus")
    readonly_fields = ("id", "created_at", "updated_at")
    inlines = [MessageInline]


@admin.register(Message)
class MessageAdmin(admin.ModelAdmin):
    list_display = ("conversation", "role", "created_at")
    search_fields = ("conversation__id", "content")
    list_filter = ("role", "created_at")
    readonly_fields = ("created_at",)
