from django.conf import settings
from django.urls import path

from .views import (
    OperatorLoginView,
    OperatorLogoutView,
    chat_home,
    operator_dashboard,
    telegram_webhook,
)

app_name = "chat"

urlpatterns = [
    path("operator/login/", OperatorLoginView.as_view(), name="operator_login"),
    path("operator/logout/", OperatorLogoutView.as_view(), name="operator_logout"),
    path("operator/", operator_dashboard, name="operator_dashboard"),
    path(settings.TELEGRAM_WEBHOOK_PATH.lstrip("/"), telegram_webhook, name="telegram_webhook"),
    path("", chat_home, name="home"),
]
