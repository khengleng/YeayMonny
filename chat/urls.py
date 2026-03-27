from django.conf import settings
from django.urls import path

from .views import chat_home, telegram_webhook

app_name = "chat"

urlpatterns = [
    path(settings.TELEGRAM_WEBHOOK_PATH.lstrip("/"), telegram_webhook, name="telegram_webhook"),
    path("", chat_home, name="home"),
]
