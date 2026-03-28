from django.contrib import admin

from .models import (
    AssistantConfig,
    AssistantConfigHistory,
    BroadcastCampaign,
    Conversation,
    Message,
    OperatorSecurityProfile,
)

admin.site.site_header = "Fortune Telling Administration"
admin.site.site_title = "Fortune Telling Administration"
admin.site.index_title = "Fortune Telling Administration"


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
        "contact_email",
        "contact_phone",
        "marketing_opt_in",
        "question_focus",
        "created_at",
        "updated_at",
    )
    search_fields = (
        "id",
        "session_key",
        "name",
        "birth_info",
        "question_focus",
        "contact_email",
        "contact_phone",
        "telegram_username",
    )
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
    change_list_template = "admin/chat/assistantconfig/change_list.html"
    list_display = (
        "id",
        "model_name",
        "temperature",
        "enable_fengshui_engine",
        "enable_face_reading_engine",
        "enable_palm_reading_engine",
        "enable_financial_advisory_engine",
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
        "enable_financial_advisory_engine",
        "compatibility_score_threshold",
        "engine_operator_note",
        "changed_by",
        "change_reason",
        "created_at",
    )

    def has_add_permission(self, request):
        return False


@admin.register(BroadcastCampaign)
class BroadcastCampaignAdmin(admin.ModelAdmin):
    list_display = ("id", "title", "channel", "status", "recipient_count", "success_count", "failure_count", "sent_at", "created_by")
    list_filter = ("channel", "status", "created_at")
    search_fields = ("title", "message", "created_by")
    readonly_fields = ("created_at", "sent_at", "recipient_count", "success_count", "failure_count")


@admin.register(OperatorSecurityProfile)
class OperatorSecurityProfileAdmin(admin.ModelAdmin):
    list_display = ("user", "is_otp_enabled", "last_verified_at", "updated_at")
    list_filter = ("is_otp_enabled",)
    search_fields = ("user__username", "user__email")
