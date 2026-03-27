import json
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from django.conf import settings
from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings
from django.urls import reverse

from .models import AssistantConfig, Conversation, Message
from .services import get_yeay_monny_reply


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


class OperatorPortalTests(TestCase):
    def setUp(self) -> None:
        user_model = get_user_model()
        self.staff_user = user_model.objects.create_user(
            username="operator",
            password="testpass123",
            is_staff=True,
        )
        self.normal_user = user_model.objects.create_user(
            username="viewer",
            password="testpass123",
            is_staff=False,
        )

    def test_operator_requires_login(self) -> None:
        response = self.client.get(reverse("chat:operator_dashboard"))
        self.assertEqual(response.status_code, 302)
        self.assertIn(reverse("chat:operator_login"), response.url)

    def test_non_staff_gets_forbidden(self) -> None:
        self.client.login(username="viewer", password="testpass123")
        response = self.client.get(reverse("chat:operator_dashboard"))
        self.assertEqual(response.status_code, 403)

    def test_staff_can_update_assistant_config(self) -> None:
        self.client.login(username="operator", password="testpass123")
        response = self.client.post(
            reverse("chat:operator_dashboard"),
            {
                "system_prompt": "prompt from operator",
                "model_name": "gpt-4.1-mini",
                "temperature": "0.4",
            },
            follow=True,
        )
        self.assertEqual(response.status_code, 200)

        config = AssistantConfig.get_solo()
        self.assertEqual(config.system_prompt, "prompt from operator")
        self.assertEqual(config.model_name, "gpt-4.1-mini")
        self.assertEqual(config.temperature, 0.4)
        self.assertEqual(config.updated_by, "operator")


@override_settings(
    OPENAI_API_KEY="fake-key",
    OPENAI_TIMEOUT_SECONDS=10,
)
class AssistantConfigServiceTests(TestCase):
    def test_service_uses_operator_config_values(self) -> None:
        config = AssistantConfig.get_solo()
        config.system_prompt = "custom system prompt"
        config.model_name = "gpt-4.1"
        config.temperature = 0.2
        config.save()

        mock_client = MagicMock()
        mock_client.responses.create.return_value = SimpleNamespace(output_text="test reply")

        history = [Message(role=Message.Role.USER, content="hello")]

        with patch("chat.services.OpenAI", return_value=mock_client):
            reply = get_yeay_monny_reply(history)

        self.assertEqual(reply, "test reply")
        mock_client.responses.create.assert_called_once()
        kwargs = mock_client.responses.create.call_args.kwargs
        self.assertEqual(kwargs["model"], "gpt-4.1")
        self.assertEqual(kwargs["temperature"], 0.2)
        self.assertEqual(kwargs["input"][0]["content"], "custom system prompt")


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
