import uuid

from django.db import models
from django.utils import timezone

from .prompts import SYSTEM_PROMPT


class Conversation(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    session_key = models.CharField(max_length=40, db_index=True)
    name = models.CharField(max_length=255, blank=True)
    birth_info = models.CharField(max_length=255, blank=True)
    question_focus = models.CharField(max_length=255, blank=True)
    contact_email = models.EmailField(blank=True)
    contact_phone = models.CharField(max_length=40, blank=True)
    telegram_username = models.CharField(max_length=255, blank=True)
    marketing_opt_in = models.BooleanField(default=False)
    marketing_opt_in_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-updated_at"]

    def __str__(self) -> str:
        return f"Conversation {self.id}"

    def apply_marketing_opt_in(self, opted_in: bool) -> None:
        self.marketing_opt_in = opted_in
        if opted_in and not self.marketing_opt_in_at:
            self.marketing_opt_in_at = timezone.now()
        if not opted_in:
            self.marketing_opt_in_at = None


class Message(models.Model):
    class Role(models.TextChoices):
        USER = "user", "User"
        ASSISTANT = "assistant", "Assistant"

    conversation = models.ForeignKey(
        Conversation,
        on_delete=models.CASCADE,
        related_name="messages",
    )
    role = models.CharField(max_length=20, choices=Role.choices)
    content = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["created_at"]

    def __str__(self) -> str:
        return f"{self.role} @ {self.created_at:%Y-%m-%d %H:%M}"


class AssistantConfig(models.Model):
    system_prompt = models.TextField(default=SYSTEM_PROMPT)
    model_name = models.CharField(max_length=100, default="gpt-4.1-mini")
    temperature = models.FloatField(default=0.8)
    enable_fengshui_engine = models.BooleanField(default=True)
    enable_face_reading_engine = models.BooleanField(default=True)
    enable_palm_reading_engine = models.BooleanField(default=True)
    enable_vehicle_numerology_engine = models.BooleanField(default=True)
    enable_house_numerology_engine = models.BooleanField(default=True)
    enable_compatibility_engine = models.BooleanField(default=True)
    enable_financial_advisory_engine = models.BooleanField(default=True)
    compatibility_score_threshold = models.PositiveSmallIntegerField(default=58)
    engine_operator_note = models.TextField(blank=True)
    updated_at = models.DateTimeField(auto_now=True)
    updated_by = models.CharField(max_length=150, blank=True)

    class Meta:
        verbose_name = "Assistant Configuration"
        verbose_name_plural = "Assistant Configuration"
        permissions = (
            ("rollback_assistantconfig", "Can rollback assistant configuration"),
            ("manage_advanced_assistantconfig", "Can manage advanced assistant settings"),
        )

    @classmethod
    def get_solo(cls) -> "AssistantConfig":
        config, _ = cls.objects.get_or_create(
            pk=1,
            defaults={
                "system_prompt": SYSTEM_PROMPT,
                "model_name": "gpt-4.1-mini",
                "temperature": 0.8,
                "enable_fengshui_engine": True,
                "enable_face_reading_engine": True,
                "enable_palm_reading_engine": True,
                "enable_vehicle_numerology_engine": True,
                "enable_house_numerology_engine": True,
                "enable_compatibility_engine": True,
                "enable_financial_advisory_engine": True,
                "compatibility_score_threshold": 58,
                "engine_operator_note": "",
            },
        )
        return config

    def save(self, *args, **kwargs):
        self.pk = 1
        super().save(*args, **kwargs)


class AssistantConfigHistory(models.Model):
    class ChangeReason(models.TextChoices):
        UPDATE = "update", "Update"
        ROLLBACK = "rollback", "Rollback"

    config = models.ForeignKey(
        AssistantConfig,
        on_delete=models.CASCADE,
        related_name="history",
    )
    system_prompt = models.TextField()
    model_name = models.CharField(max_length=100)
    temperature = models.FloatField()
    enable_fengshui_engine = models.BooleanField(default=True)
    enable_face_reading_engine = models.BooleanField(default=True)
    enable_palm_reading_engine = models.BooleanField(default=True)
    enable_vehicle_numerology_engine = models.BooleanField(default=True)
    enable_house_numerology_engine = models.BooleanField(default=True)
    enable_compatibility_engine = models.BooleanField(default=True)
    enable_financial_advisory_engine = models.BooleanField(default=True)
    compatibility_score_threshold = models.PositiveSmallIntegerField(default=58)
    engine_operator_note = models.TextField(blank=True)
    changed_by = models.CharField(max_length=150, blank=True)
    change_reason = models.CharField(max_length=20, choices=ChangeReason.choices, default=ChangeReason.UPDATE)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]
        verbose_name = "Assistant Configuration History"
        verbose_name_plural = "Assistant Configuration History"

    def __str__(self) -> str:
        return f"{self.get_change_reason_display()} @ {self.created_at:%Y-%m-%d %H:%M}"

    @classmethod
    def snapshot(
        cls,
        *,
        config: AssistantConfig,
        changed_by: str,
        change_reason: str = ChangeReason.UPDATE,
    ) -> "AssistantConfigHistory":
        return cls.objects.create(
            config=config,
            system_prompt=config.system_prompt,
            model_name=config.model_name,
            temperature=config.temperature,
            enable_fengshui_engine=config.enable_fengshui_engine,
            enable_face_reading_engine=config.enable_face_reading_engine,
            enable_palm_reading_engine=config.enable_palm_reading_engine,
            enable_vehicle_numerology_engine=config.enable_vehicle_numerology_engine,
            enable_house_numerology_engine=config.enable_house_numerology_engine,
            enable_compatibility_engine=config.enable_compatibility_engine,
            enable_financial_advisory_engine=config.enable_financial_advisory_engine,
            compatibility_score_threshold=config.compatibility_score_threshold,
            engine_operator_note=config.engine_operator_note,
            changed_by=changed_by,
            change_reason=change_reason,
        )
