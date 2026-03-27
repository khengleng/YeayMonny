import uuid

from django.db import models

from .prompts import SYSTEM_PROMPT


class Conversation(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    session_key = models.CharField(max_length=40, db_index=True)
    name = models.CharField(max_length=255, blank=True)
    birth_info = models.CharField(max_length=255, blank=True)
    question_focus = models.CharField(max_length=255, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-updated_at"]

    def __str__(self) -> str:
        return f"Conversation {self.id}"


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
    updated_at = models.DateTimeField(auto_now=True)
    updated_by = models.CharField(max_length=150, blank=True)

    class Meta:
        verbose_name = "Assistant Configuration"
        verbose_name_plural = "Assistant Configuration"

    @classmethod
    def get_solo(cls) -> "AssistantConfig":
        config, _ = cls.objects.get_or_create(
            pk=1,
            defaults={
                "system_prompt": SYSTEM_PROMPT,
                "model_name": "gpt-4.1-mini",
                "temperature": 0.8,
            },
        )
        return config

    def save(self, *args, **kwargs):
        self.pk = 1
        super().save(*args, **kwargs)
