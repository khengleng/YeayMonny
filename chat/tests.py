import json
from unittest.mock import patch

from django.conf import settings
from django.test import TestCase, override_settings
from django.urls import reverse

from .models import Conversation, Message


class ChatViewTests(TestCase):
    def test_home_loads_with_first_message(self) -> None:
        response = self.client.get(reverse("chat:home"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "យាយមុន្នី")

    @patch("chat.views.get_yeay_monny_reply", return_value="សួស្តី កូនអើយ")
    def test_post_creates_user_and_assistant_messages(self, _mock_reply) -> None:
        response = self.client.post(
            reverse("chat:home"),
            {
                "name": "ស្រីពៅ",
                "birth_info": "2000",
                "question_focus": "ការងារ",
                "message": "ខ្ញុំចង់សួរពីការងារ",
            },
        )
        self.assertEqual(response.status_code, 302)
        self.assertEqual(Conversation.objects.count(), 1)
        self.assertEqual(Message.objects.count(), 2)

        conversation = Conversation.objects.first()
        assert conversation is not None
        self.assertEqual(conversation.name, "ស្រីពៅ")
        self.assertEqual(conversation.birth_info, "2000")
        self.assertEqual(conversation.question_focus, "ការងារ")


@override_settings(
    TELEGRAM_BOT_TOKEN="test-token",
    TELEGRAM_WEBHOOK_SECRET="secret-token",
    TELEGRAM_WEBHOOK_PATH="/webhooks/telegram/",
)
class TelegramWebhookTests(TestCase):
    @patch("chat.views.send_telegram_message")
    @patch("chat.views.get_yeay_monny_reply", return_value="យាយសូមជូនពរ")
    def test_telegram_webhook_creates_messages_and_replies(self, _mock_reply, mock_send) -> None:
        payload = {
            "message": {
                "chat": {"id": 123456},
                "text": "ខ្ញុំចង់ដឹងពីការងារ",
            }
        }

        response = self.client.post(
            reverse("chat:telegram_webhook"),
            data=json.dumps(payload),
            content_type="application/json",
            HTTP_X_TELEGRAM_BOT_API_SECRET_TOKEN="secret-token",
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(Conversation.objects.filter(session_key="tg_123456").count(), 1)
        self.assertEqual(Message.objects.count(), 2)
        mock_send.assert_called_once_with(123456, "យាយសូមជូនពរ")

    def test_telegram_webhook_rejects_invalid_secret(self) -> None:
        payload = {"message": {"chat": {"id": 1}, "text": "hello"}}

        response = self.client.post(
            reverse("chat:telegram_webhook"),
            data=json.dumps(payload),
            content_type="application/json",
            HTTP_X_TELEGRAM_BOT_API_SECRET_TOKEN="wrong",
        )

        self.assertEqual(response.status_code, 403)


class TelegramPathNormalizationTests(TestCase):
    def test_webhook_path_normalized(self) -> None:
        self.assertTrue(settings.TELEGRAM_WEBHOOK_PATH.startswith("/"))
        self.assertTrue(settings.TELEGRAM_WEBHOOK_PATH.endswith("/"))
