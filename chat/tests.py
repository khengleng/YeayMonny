import json
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from django.conf import settings
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Permission
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings
from django.urls import reverse
from openai import OpenAIError

from .models import AssistantConfig, AssistantConfigHistory, Conversation, Message
from .services import KHMER_ONLY_FALLBACK, get_yeay_monny_reply


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

    @patch("chat.views.get_yeay_monny_reply", return_value="នេះជាចម្លើយពីយាយ")
    @patch("chat.views.analyze_image_bytes", return_value="យាយមើលឃើញរូបមនុស្សនៅកន្លែងការងារ")
    @patch("chat.views.transcribe_audio_bytes", return_value="ខ្ញុំចង់សួររឿងការងារ")
    def test_post_with_voice_and_image_builds_combined_user_context(
        self,
        _mock_transcribe,
        _mock_image,
        _mock_reply,
    ) -> None:
        image = SimpleUploadedFile("photo.jpg", b"fake-image-bytes", content_type="image/jpeg")
        voice = SimpleUploadedFile("voice.ogg", b"fake-voice-bytes", content_type="audio/ogg")

        response = self.client.post(
            reverse("chat:home"),
            {
                "name": "សុភា",
                "message": "",
                "image": image,
                "voice": voice,
            },
        )
        self.assertEqual(response.status_code, 302)
        self.assertEqual(Message.objects.count(), 2)
        user_message = Message.objects.filter(role=Message.Role.USER).first()
        assert user_message is not None
        self.assertIn("អត្ថបទបានបម្លែងពីសម្លេង", user_message.content)
        self.assertIn("ការពិពណ៌នារូបភាពសម្រាប់មើលជោគជាតា", user_message.content)


class OperatorPortalTests(TestCase):
    def setUp(self) -> None:
        user_model = get_user_model()
        self.editor_user = user_model.objects.create_user(
            username="editor",
            password="testpass123",
        )
        self.admin_user = user_model.objects.create_user(
            username="admin",
            password="testpass123",
        )
        self.normal_user = user_model.objects.create_user(
            username="viewer",
            password="testpass123",
        )
        self._grant_permissions()

    def _grant_permissions(self) -> None:
        self.editor_user.user_permissions.add(self._perm("view_assistantconfig"))
        self.editor_user.user_permissions.add(self._perm("change_assistantconfig"))

        self.admin_user.user_permissions.add(self._perm("view_assistantconfig"))
        self.admin_user.user_permissions.add(self._perm("change_assistantconfig"))
        self.admin_user.user_permissions.add(self._perm("manage_advanced_assistantconfig"))
        self.admin_user.user_permissions.add(self._perm("rollback_assistantconfig"))

    def _perm(self, codename: str) -> Permission:
        return Permission.objects.get(codename=codename)

    def test_operator_login_supports_email(self) -> None:
        self.admin_user.email = "admin@example.com"
        self.admin_user.save(update_fields=["email"])
        response = self.client.post(
            reverse("chat:operator_login"),
            {"username": "admin@example.com", "password": "testpass123"},
        )
        self.assertEqual(response.status_code, 302)
        self.assertIn(reverse("chat:operator_dashboard"), response.url)

    def test_non_operator_login_is_rejected_from_operator_portal(self) -> None:
        response = self.client.post(
            reverse("chat:operator_login"),
            {"username": "viewer", "password": "testpass123"},
            follow=True,
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "មិនទាន់មានសិទ្ធិប្រើផ្ទាំងប្រតិបត្តិការ")

    def test_operator_logout_requires_post(self) -> None:
        self.client.login(username="admin", password="testpass123")
        get_response = self.client.get(reverse("chat:operator_logout"))
        self.assertEqual(get_response.status_code, 405)

        post_response = self.client.post(reverse("chat:operator_logout"))
        self.assertEqual(post_response.status_code, 302)
        self.assertIn(reverse("chat:operator_login"), post_response.url)

    def test_operator_requires_login(self) -> None:
        response = self.client.get(reverse("chat:operator_dashboard"))
        self.assertEqual(response.status_code, 302)
        self.assertIn(reverse("chat:operator_login"), response.url)

    def test_non_operator_gets_forbidden(self) -> None:
        self.client.login(username="viewer", password="testpass123")
        response = self.client.get(reverse("chat:operator_dashboard"))
        self.assertEqual(response.status_code, 403)

    def test_editor_can_update_prompt_only(self) -> None:
        self.client.login(username="editor", password="testpass123")
        response = self.client.post(
            reverse("chat:operator_dashboard"),
            {
                "action": "save_prompt",
                "system_prompt": "prompt from operator",
            },
            follow=True,
        )
        self.assertEqual(response.status_code, 200)

        config = AssistantConfig.get_solo()
        self.assertEqual(config.system_prompt, "prompt from operator")
        self.assertEqual(config.updated_by, "editor")
        self.assertEqual(
            AssistantConfigHistory.objects.filter(change_reason=AssistantConfigHistory.ChangeReason.UPDATE).count(),
            1,
        )

        advanced_response = self.client.post(
            reverse("chat:operator_dashboard"),
            {
                "action": "save_advanced",
                "model_name": "gpt-4.1",
                "temperature": "0.3",
            },
        )
        self.assertEqual(advanced_response.status_code, 403)

    def test_operator_dashboard_shows_operations_section(self) -> None:
        self.client.login(username="admin", password="testpass123")
        response = self.client.get(reverse("chat:operator_dashboard"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "ផ្ទាំងប្រតិបត្តិការ")

    def test_operator_can_open_conversation_detail(self) -> None:
        conversation = Conversation.objects.create(session_key="abc123", name="Test User")
        Message.objects.create(conversation=conversation, role=Message.Role.USER, content="hello")
        self.client.login(username="admin", password="testpass123")
        response = self.client.get(
            reverse("chat:operator_conversation_detail", kwargs={"conversation_id": conversation.id})
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "សន្ទនាលម្អិត")
        self.assertContains(response, "hello")

    def test_admin_can_update_advanced_and_rollback(self) -> None:
        self.client.login(username="admin", password="testpass123")

        self.client.post(
            reverse("chat:operator_dashboard"),
            {
                "action": "save_prompt",
                "system_prompt": "prompt A",
            },
            follow=True,
        )
        self.client.post(
            reverse("chat:operator_dashboard"),
            {
                "action": "save_prompt",
                "system_prompt": "prompt B",
            },
            follow=True,
        )
        self.client.post(
            reverse("chat:operator_dashboard"),
            {
                "action": "save_advanced",
                "model_name": "gpt-4.1",
                "temperature": "0.2",
            },
            follow=True,
        )

        version = AssistantConfigHistory.objects.filter(system_prompt="prompt A").first()
        assert version is not None
        rollback_response = self.client.post(
            reverse("chat:operator_dashboard"),
            {
                "action": "rollback",
                "version_id": str(version.id),
            },
            follow=True,
        )
        self.assertEqual(rollback_response.status_code, 200)
        config = AssistantConfig.get_solo()
        self.assertEqual(config.system_prompt, "prompt A")
        self.assertEqual(config.updated_by, "admin")
        self.assertEqual(config.model_name, version.model_name)
        self.assertEqual(config.temperature, version.temperature)
        self.assertTrue(
            AssistantConfigHistory.objects.filter(
                change_reason=AssistantConfigHistory.ChangeReason.ROLLBACK
            ).exists()
        )


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
        mock_client.responses.create.return_value = SimpleNamespace(output_text="នេះជាចម្លើយតេស្ត")

        history = [Message(role=Message.Role.USER, content="hello")]

        with patch("chat.services.OpenAI", return_value=mock_client):
            reply = get_yeay_monny_reply(history)

        self.assertEqual(reply, "នេះជាចម្លើយតេស្ត")
        mock_client.responses.create.assert_called_once()
        kwargs = mock_client.responses.create.call_args.kwargs
        self.assertEqual(kwargs["model"], "gpt-4.1")
        self.assertEqual(kwargs["temperature"], 0.2)
        self.assertEqual(kwargs["input"][0]["content"], "custom system prompt")

    def test_service_rewrites_non_khmer_reply(self) -> None:
        config = AssistantConfig.get_solo()
        config.model_name = "gpt-4.1"
        config.temperature = 0.5
        config.save()

        mock_client = MagicMock()
        mock_client.responses.create.side_effect = [
            SimpleNamespace(output_text="This is English output."),
            SimpleNamespace(output_text="នេះជាចម្លើយជាភាសាខ្មែរ។"),
        ]

        history = [Message(role=Message.Role.USER, content="test")]
        with patch("chat.services.OpenAI", return_value=mock_client):
            reply = get_yeay_monny_reply(history)

        self.assertEqual(reply, "នេះជាចម្លើយជាភាសាខ្មែរ។")
        self.assertEqual(mock_client.responses.create.call_count, 2)

    def test_service_returns_khmer_fallback_when_rewrite_fails(self) -> None:
        mock_client = MagicMock()
        mock_client.responses.create.side_effect = [
            SimpleNamespace(output_text="Hello in English"),
            OpenAIError("rewrite failed"),
        ]

        history = [Message(role=Message.Role.USER, content="test")]
        with patch("chat.services.OpenAI", return_value=mock_client):
            reply = get_yeay_monny_reply(history)

        self.assertEqual(reply, KHMER_ONLY_FALLBACK)

    def test_service_rewrites_repetitive_reply(self) -> None:
        mock_client = MagicMock()
        mock_client.responses.create.side_effect = [
            SimpleNamespace(output_text="យាយសូមណែនាំដដែល"),
            SimpleNamespace(output_text="កូនអើយ លើកនេះយាយសូមប្តូររបៀបណែនាំឱ្យសមស្ថានភាពកូន។"),
        ]

        history = [
            Message(role=Message.Role.USER, content="ជួយមើលការងារ"),
            Message(role=Message.Role.ASSISTANT, content="យាយសូមណែនាំដដែល"),
        ]
        with patch("chat.services.OpenAI", return_value=mock_client):
            reply = get_yeay_monny_reply(history)

        self.assertEqual(reply, "កូនអើយ លើកនេះយាយសូមប្តូររបៀបណែនាំឱ្យសមស្ថានភាពកូន។")
        self.assertEqual(mock_client.responses.create.call_count, 2)


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

    @patch("chat.views.send_telegram_message")
    @patch("chat.views.get_yeay_monny_reply", return_value="យាយឆ្លើយពីរូបភាព")
    @patch("chat.views.analyze_image_bytes", return_value="យាយឃើញទិដ្ឋភាពស្ងប់")
    @patch("chat.views.fetch_telegram_file", return_value=(b"img", "image/jpeg", "photo.jpg"))
    def test_telegram_webhook_supports_photo(
        self,
        _mock_fetch,
        _mock_analyze,
        _mock_reply,
        mock_send,
    ) -> None:
        payload = {
            "message": {
                "chat": {"id": 77},
                "caption": "សូមមើលរូបនេះ",
                "photo": [{"file_id": "a1"}, {"file_id": "a2"}],
            }
        }
        response = self.client.post(
            reverse("chat:telegram_webhook"),
            data=json.dumps(payload),
            content_type="application/json",
            HTTP_X_TELEGRAM_BOT_API_SECRET_TOKEN="secret-token",
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(Message.objects.filter(conversation__session_key="tg_77").count(), 2)
        mock_send.assert_called_once()

    @patch("chat.views.send_telegram_message")
    @patch("chat.views.get_yeay_monny_reply", return_value="យាយឆ្លើយពីសម្លេង")
    @patch("chat.views.transcribe_audio_bytes", return_value="ខ្ញុំសួរពីស្នេហា")
    @patch("chat.views.fetch_telegram_file", return_value=(b"audio", "audio/ogg", "voice.ogg"))
    def test_telegram_webhook_supports_voice(
        self,
        _mock_fetch,
        _mock_transcribe,
        _mock_reply,
        mock_send,
    ) -> None:
        payload = {
            "message": {
                "chat": {"id": 88},
                "voice": {"file_id": "v1"},
            }
        }
        response = self.client.post(
            reverse("chat:telegram_webhook"),
            data=json.dumps(payload),
            content_type="application/json",
            HTTP_X_TELEGRAM_BOT_API_SECRET_TOKEN="secret-token",
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(Message.objects.filter(conversation__session_key="tg_88").count(), 2)
        mock_send.assert_called_once()


class TelegramPathNormalizationTests(TestCase):
    def test_webhook_path_normalized(self) -> None:
        self.assertTrue(settings.TELEGRAM_WEBHOOK_PATH.startswith("/"))
        self.assertTrue(settings.TELEGRAM_WEBHOOK_PATH.endswith("/"))
