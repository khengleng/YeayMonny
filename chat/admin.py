from django.contrib import admin

from .models import AssistantConfig, AssistantConfigHistory, Conversation, Message


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


@admin.register(AssistantConfig)
class AssistantConfigAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "model_name",
        "temperature",
        "enable_fengshui_engine",
        "enable_face_reading_engine",
        "enable_palm_reading_engine",
        "updated_at",
        "updated_by",
    )
    readonly_fields = ("updated_at",)

    def has_add_permission(self, request):
        return not AssistantConfig.objects.exists()


@admin.register(AssistantConfigHistory)
class AssistantConfigHistoryAdmin(admin.ModelAdmin):
    list_display = ("id", "change_reason", "model_name", "temperature", "enable_compatibility_engine", "changed_by", "created_at")
    list_filter = ("change_reason", "created_at")
    search_fields = ("changed_by", "model_name", "system_prompt")
    readonly_fields = (
        "config",
        "system_prompt",
        "model_name",
        "temperature",
        "enable_fengshui_engine",
        "enable_face_reading_engine",
        "enable_palm_reading_engine",
        "enable_vehicle_numerology_engine",
        "enable_house_numerology_engine",
        "enable_compatibility_engine",
        "compatibility_score_threshold",
        "engine_operator_note",
        "changed_by",
        "change_reason",
        "created_at",
    )

    def has_add_permission(self, request):
        return False
