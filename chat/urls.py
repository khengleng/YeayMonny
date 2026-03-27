from django.conf import settings
from django.urls import path

from .views import (
    OperatorLoginView,
    chat_home,
    operator_conversation_detail,
    operator_dashboard,
    operator_export_contacts_csv,
    operator_logout,
    telegram_webhook,
)

app_name = "chat"

urlpatterns = [
    path("operator/login/", OperatorLoginView.as_view(), name="operator_login"),
    path("operator/logout/", operator_logout, name="operator_logout"),
    path("operator/", operator_dashboard, name="operator_dashboard"),
    path("operator/contacts/export.csv", operator_export_contacts_csv, name="operator_export_contacts_csv"),
    path(
        "operator/conversations/<uuid:conversation_id>/",
        operator_conversation_detail,
        name="operator_conversation_detail",
    ),
    path(settings.TELEGRAM_WEBHOOK_PATH.lstrip("/"), telegram_webhook, name="telegram_webhook"),
    path("", chat_home, name="home"),
]
