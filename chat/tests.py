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

from .face_reading import build_face_reading_engine_notes
from .fengshui import build_fengshui_snapshot
from .house_numerology import build_house_numerology_snapshot
from .models import AssistantConfig, AssistantConfigHistory, Conversation, Message
from .palm_reading import build_palm_reading_engine_notes
from .services import KHMER_ONLY_FALLBACK, get_yeay_monny_reply
from .vehicle_numerology import build_vehicle_numerology_snapshot
from .compatibility import build_compatibility_snapshot
from .financial_advisory import build_financial_advisory_snapshot


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

    @patch("chat.views.get_yeay_monny_reply", return_value="ចម្លើយ")
    def test_post_saves_contact_and_marketing_opt_in(self, _mock_reply) -> None:
        self.client.post(
            reverse("chat:home"),
            {
                "name": "ស្រីពៅ",
                "contact_email": "test@example.com",
                "contact_phone": "012345678",
                "marketing_opt_in": "on",
                "message": "ជួយមើល",
            },
        )
        convo = Conversation.objects.first()
        assert convo is not None
        self.assertEqual(convo.contact_email, "test@example.com")
        self.assertEqual(convo.contact_phone, "012345678")
        self.assertTrue(convo.marketing_opt_in)
        self.assertIsNotNone(convo.marketing_opt_in_at)

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

    @patch("chat.views.transcribe_audio_bytes", return_value="")
    def test_web_voice_unclear_asks_for_text(self, _mock_transcribe) -> None:
        voice = SimpleUploadedFile("voice.ogg", b"fake-voice-bytes", content_type="audio/ogg")
        response = self.client.post(
            reverse("chat:home"),
            {
                "message": "",
                "voice": voice,
            },
            follow=True,
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "អក្សរងាយឱ្យយាយមើលបានច្បាស់ជាងសម្លេង")
        self.assertEqual(Message.objects.count(), 0)


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

    def test_admin_can_update_engine_settings(self) -> None:
        self.client.login(username="admin", password="testpass123")
        response = self.client.post(
            reverse("chat:operator_dashboard"),
            {
                "action": "save_engines",
                "enable_fengshui_engine": "",
                "enable_face_reading_engine": "on",
                "enable_palm_reading_engine": "",
                "enable_vehicle_numerology_engine": "on",
                "enable_house_numerology_engine": "on",
                "enable_compatibility_engine": "",
                "compatibility_score_threshold": "70",
                "engine_operator_note": "សូមឆ្លើយខ្លី និងមិនឱ្យខ្លាច",
            },
            follow=True,
        )
        self.assertEqual(response.status_code, 200)
        config = AssistantConfig.get_solo()
        self.assertFalse(config.enable_fengshui_engine)
        self.assertTrue(config.enable_face_reading_engine)
        self.assertFalse(config.enable_palm_reading_engine)
        self.assertFalse(config.enable_compatibility_engine)
        self.assertEqual(config.compatibility_score_threshold, 70)
        self.assertIn("មិនឱ្យខ្លាច", config.engine_operator_note)

    def test_operator_dashboard_shows_operations_section(self) -> None:
        self.client.login(username="admin", password="testpass123")
        response = self.client.get(reverse("chat:operator_dashboard"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "ផ្ទាំងប្រតិបត្តិការ")
        self.assertContains(response, "ទិន្នន័យផ្សព្វផ្សាយ")

    def test_admin_can_export_contacts_csv(self) -> None:
        Conversation.objects.create(
            session_key="abc",
            name="User",
            contact_email="user@example.com",
            marketing_opt_in=True,
        )
        self.client.login(username="admin", password="testpass123")
        response = self.client.get(reverse("chat:operator_export_contacts_csv"))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response["Content-Type"], "text/csv; charset=utf-8")
        self.assertIn("user@example.com", response.content.decode("utf-8"))

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

        self.assertIn("នេះជាចម្លើយតេស្ត", reply)
        self.assertIn("ចៅ", reply)
        mock_client.responses.create.assert_called_once()
        kwargs = mock_client.responses.create.call_args.kwargs
        self.assertEqual(kwargs["model"], "gpt-4.1")
        self.assertEqual(kwargs["temperature"], 0.2)
        self.assertEqual(kwargs["input"][0]["content"], "custom system prompt")

    def test_service_injects_user_profile_context(self) -> None:
        mock_client = MagicMock()
        mock_client.responses.create.return_value = SimpleNamespace(output_text="ចម្លើយ")
        history = [Message(role=Message.Role.USER, content="សួស្តី")]
        profile = {
            "name": "សុភា",
            "birth_info": "១៩៩៨",
            "question_focus": "ការងារ",
        }
        with patch("chat.services.OpenAI", return_value=mock_client):
            get_yeay_monny_reply(history, user_profile=profile)

        kwargs = mock_client.responses.create.call_args.kwargs
        profile_block = kwargs["input"][1]["content"]
        self.assertIn("សុភា", profile_block)
        self.assertIn("១៩៩៨", profile_block)
        self.assertIn("ការងារ", profile_block)
        self.assertIn("ឆ្នាំចិន", profile_block)
        self.assertIn("លេខផ្លូវជីវិត", profile_block)
        self.assertIn("WOFS", profile_block)
        self.assertIn("លេខក្វា", profile_block)
        self.assertIn("Flying Star ប្រចាំឆ្នាំ", profile_block)
        self.assertIn("ទិសល្អប្រចាំឆ្នាំ", profile_block)
        self.assertIn("TravelChinaGuide style", profile_block)
        self.assertIn("ផ្លាកលេខរថយន្ត", profile_block)
        self.assertIn("លេខផ្ទះ", profile_block)
        self.assertIn("Compatibility Engine", profile_block)
        self.assertIn("Financial Advisory Engine", profile_block)

    def test_service_profile_context_respects_engine_toggles(self) -> None:
        config = AssistantConfig.get_solo()
        config.enable_fengshui_engine = False
        config.enable_vehicle_numerology_engine = False
        config.enable_house_numerology_engine = False
        config.enable_compatibility_engine = False
        config.engine_operator_note = "ឆ្លើយអោយទន់ភ្លន់"
        config.save()

        mock_client = MagicMock()
        mock_client.responses.create.return_value = SimpleNamespace(output_text="ចម្លើយ")
        history = [Message(role=Message.Role.USER, content="សួស្តី")]
        with patch("chat.services.OpenAI", return_value=mock_client):
            get_yeay_monny_reply(history, user_profile={"birth_info": "1998"})

        profile_block = mock_client.responses.create.call_args.kwargs["input"][1]["content"]
        self.assertIn("ម៉ាស៊ីន Feng Shui ត្រូវបានបិទ", profile_block)
        self.assertIn("ម៉ាស៊ីនលេខផ្លាករថយន្តត្រូវបានបិទ", profile_block)
        self.assertIn("ម៉ាស៊ីនភាពត្រូវគ្នាស្នេហាត្រូវបានបិទ", profile_block)
        self.assertIn("ឆ្លើយអោយទន់ភ្លន់", profile_block)


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

        self.assertIn("នេះជាចម្លើយជាភាសាខ្មែរ។", reply)
        self.assertIn("ចៅ", reply)
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

        self.assertIn("លើកនេះយាយសូមប្តូររបៀបណែនាំឱ្យសមស្ថានភាពកូន។", reply)
        self.assertIn("ចៅ", reply)
        self.assertEqual(mock_client.responses.create.call_count, 2)

    def test_service_rewrites_near_duplicate_reply(self) -> None:
        mock_client = MagicMock()
        mock_client.responses.create.side_effect = [
            SimpleNamespace(output_text="កូនអើយ យាយឃើញថាពេលនេះការងារអ្នកត្រូវការការប្រុងប្រយ័ត្ន និងស្ងប់ចិត្ត។"),
            SimpleNamespace(output_text="កូនសម្លាញ់ យាយសូមណែនាំឱ្យដោះស្រាយការងារម្តងមួយជំហាន ដោយរក្សាចិត្តឱ្យត្រជាក់។"),
        ]

        history = [
            Message(
                role=Message.Role.ASSISTANT,
                content="កូនអើយ យាយឃើញថាពេលនេះការងារអ្នកត្រូវការការប្រុងប្រយ័ត្ន ហើយត្រូវស្ងប់ចិត្ត។",
            )
        ]

        with patch("chat.services.OpenAI", return_value=mock_client):
            reply = get_yeay_monny_reply(history)

        self.assertIn("កូនសម្លាញ់ យាយសូមណែនាំឱ្យដោះស្រាយការងារម្តងមួយជំហាន ដោយរក្សាចិត្តឱ្យត្រជាក់។", reply)
        self.assertIn("ចៅ", reply)
        self.assertEqual(mock_client.responses.create.call_count, 2)


class FengShuiEngineTests(TestCase):
    def test_build_snapshot_includes_wofs_style_signals(self) -> None:
        snapshot = build_fengshui_snapshot("12-05-1998", reference_year=2026, partner_birth_info="1994")
        self.assertEqual(snapshot.kua_male, 2)
        self.assertEqual(snapshot.kua_female, 4)
        self.assertEqual(snapshot.annual_center_star, 1)
        assert snapshot.annual_star_layout is not None
        self.assertEqual(snapshot.annual_star_layout["មជ្ឈមណ្ឌល"], 1)
        self.assertTrue(snapshot.annual_good_sectors)
        self.assertTrue(snapshot.annual_caution_sectors)
        self.assertEqual(snapshot.partner_animal, "ឆ្កែ")
        self.assertIn("ចន្លោះ៤ឆ្នាំ", snapshot.partner_relation or "")

    def test_build_snapshot_without_birth_still_has_annual_chart(self) -> None:
        snapshot = build_fengshui_snapshot("", reference_year=2026)
        self.assertIsNone(snapshot.year)
        self.assertEqual(snapshot.annual_center_star, 1)
        self.assertTrue(snapshot.annual_star_layout)
        self.assertTrue(snapshot.tai_sui_direction)


class FaceReadingEngineTests(TestCase):
    def test_face_engine_adds_zone_based_notes(self) -> None:
        text = "រូបមុខនេះមានថ្ងាសទូលាយ ភ្នែកភ្លឺ ច្រមុះត្រង់ មាត់សមស្រប និងចង្កាមូល។"
        notes = build_face_reading_engine_notes(text)
        self.assertIn("ថ្ងាស", notes)
        self.assertIn("ភ្នែក", notes)
        self.assertIn("ច្រមុះ", notes)
        self.assertIn("មាត់", notes)
        self.assertIn("ចង្កា", notes)

    def test_face_engine_ignores_non_face_context(self) -> None:
        text = "រូបនេះជាទេសភាពភ្នំ និងមេឃ មិនឃើញមុខមនុស្ស។"
        notes = build_face_reading_engine_notes(text)
        self.assertEqual(notes, "")


class PalmReadingEngineTests(TestCase):
    def test_palm_engine_adds_line_based_notes(self) -> None:
        text = "រូបបាតដៃនេះឃើញបន្ទាត់បេះដូងវែង បន្ទាត់គំនិតត្រង់ បន្ទាត់ជីវិតជ្រៅ និងបន្ទាត់វាសនាច្បាស់។"
        notes = build_palm_reading_engine_notes(text)
        self.assertIn("បន្ទាត់បេះដូង", notes)
        self.assertIn("បន្ទាត់គំនិត", notes)
        self.assertIn("បន្ទាត់ជីវិត", notes)
        self.assertIn("បន្ទាត់វាសនា", notes)

    def test_palm_engine_ignores_non_palm_context(self) -> None:
        text = "រូបនេះមិនឃើញបាតដៃទេ ជាទេសភាពធម្មជាតិ។"
        notes = build_palm_reading_engine_notes(text)
        self.assertEqual(notes, "")


class VehicleNumerologyTests(TestCase):
    def test_vehicle_number_snapshot_extracts_root_number(self) -> None:
        snap = build_vehicle_numerology_snapshot("ចៅចង់មើលផ្លាកលេខ 2AB-3456", life_path_number=6)
        self.assertEqual(snap.plate_raw, "2AB-3456")
        self.assertEqual(snap.total_value, 23)
        self.assertEqual(snap.root_number, 5)
        self.assertTrue(snap.meaning)

    def test_vehicle_snapshot_empty_when_no_plate(self) -> None:
        snap = build_vehicle_numerology_snapshot("ចៅសួររឿងការងារ")
        self.assertIsNone(snap.plate_raw)
        self.assertIsNone(snap.root_number)


class HouseNumerologyTests(TestCase):
    def test_house_snapshot_uses_moving_number_from_slash_address(self) -> None:
        snap = build_house_numerology_snapshot("ចៅសូមមើលផ្ទះលេខ 14/18")
        self.assertEqual(snap.raw_candidate, "14/18")
        self.assertEqual(snap.moving_part, "18")
        self.assertEqual(snap.total_value, 9)
        self.assertEqual(snap.root_number, 9)

    def test_house_snapshot_for_letter_suffix(self) -> None:
        snap = build_house_numerology_snapshot("ផ្ទះខ្ញុំ 47A")
        self.assertEqual(snap.moving_part, "47A")
        self.assertEqual(snap.total_value, 12)
        self.assertEqual(snap.root_number, 3)


class CompatibilityEngineTests(TestCase):
    def test_compatibility_snapshot_with_partner_year(self) -> None:
        snap = build_compatibility_snapshot(
            user_birth_info="12-05-1998",
            question_focus="ស្នេហាជាមួយគាត់ 1994 ត្រូវគ្នាទេ",
            latest_user_text="",
        )
        self.assertEqual(snap.partner_year, 1994)
        self.assertTrue(snap.score is not None)
        self.assertTrue(snap.level)
        self.assertTrue(snap.key_notes)

    def test_compatibility_snapshot_without_partner(self) -> None:
        snap = build_compatibility_snapshot(
            user_birth_info="1998",
            question_focus="ចៅចង់ដឹងស្នេហា",
            latest_user_text="",
        )
        self.assertIsNone(snap.partner_year)
        self.assertIsNone(snap.score)


class FinancialAdvisoryEngineTests(TestCase):
    def test_financial_engine_includes_goal_loan_deposit_bond_advice(self) -> None:
        snap = build_financial_advisory_snapshot(
            question_focus="ចង់ពង្រីក business និងវិនិយោគ",
            latest_user_text="ខ្ញុំមាន goal ចង់សន្សំទិញផ្ទះ តើគួរខ្ចីទុនទេ",
            life_path_number=4,
        )
        joined = " | ".join(snap.actions or [])
        self.assertIn("goal saving", joined)
        self.assertIn("loan", joined)
        self.assertIn("high-interest deposit", joined)
        self.assertIn("bond", joined)


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

    @patch("chat.views.send_telegram_message")
    @patch("chat.views.get_yeay_monny_reply", return_value="យាយបានទទួលសម្លេងហើយ")
    @patch("chat.views.transcribe_audio_bytes", return_value="")
    @patch("chat.views.fetch_telegram_file", return_value=(b"audio", "audio/ogg", "voice.ogg"))
    def test_telegram_webhook_unclear_voice_with_text_still_accepted(
        self,
        _mock_fetch,
        _mock_transcribe,
        _mock_reply,
        mock_send,
    ) -> None:
        payload = {
            "message": {
                "chat": {"id": 99},
                "text": "សួររឿងស្នេហា",
                "voice": {"file_id": "v2"},
            }
        }
        response = self.client.post(
            reverse("chat:telegram_webhook"),
            data=json.dumps(payload),
            content_type="application/json",
            HTTP_X_TELEGRAM_BOT_API_SECRET_TOKEN="secret-token",
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(Message.objects.filter(conversation__session_key="tg_99").count(), 2)
        user_message = Message.objects.filter(conversation__session_key="tg_99", role=Message.Role.USER).first()
        assert user_message is not None
        self.assertIn("សំណួររបស់អ្នកប្រើ", user_message.content)
        self.assertIn("បានផ្ញើសម្លេង", user_message.content)
        mock_send.assert_called_once()

    @patch("chat.views.send_telegram_message")
    @patch("chat.views.transcribe_audio_bytes", return_value="")
    @patch("chat.views.fetch_telegram_file", return_value=(b"audio", "audio/ogg", "voice.ogg"))
    def test_telegram_unclear_voice_without_text_requests_text_message(
        self,
        _mock_fetch,
        _mock_transcribe,
        mock_send,
    ) -> None:
        payload = {
            "message": {
                "chat": {"id": 101},
                "voice": {"file_id": "v3"},
            }
        }
        response = self.client.post(
            reverse("chat:telegram_webhook"),
            data=json.dumps(payload),
            content_type="application/json",
            HTTP_X_TELEGRAM_BOT_API_SECRET_TOKEN="secret-token",
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(Message.objects.filter(conversation__session_key="tg_101").count(), 0)
        sent_text = mock_send.call_args.args[1]
        self.assertIn("សូមសរសេរជាអក្សរ", sent_text)
        self.assertIn("អក្សរងាយ", sent_text)

    @patch("chat.views.send_telegram_message")
    @patch("chat.views.get_yeay_monny_reply", return_value="យាយឆ្លើយពីរូបភាពឯកសារ")
    @patch("chat.views.analyze_image_bytes", return_value="យាយឃើញរូបជាវត្ថុពណ៌ក្រហម")
    @patch("chat.views.fetch_telegram_file", return_value=(b"img", "image/png", "photo.png"))
    def test_telegram_webhook_supports_image_document(
        self,
        _mock_fetch,
        _mock_analyze,
        _mock_reply,
        mock_send,
    ) -> None:
        payload = {
            "message": {
                "chat": {"id": 100},
                "caption": "សូមមើលរូបឯកសារ",
                "document": {"file_id": "doc1", "mime_type": "image/png"},
            }
        }
        response = self.client.post(
            reverse("chat:telegram_webhook"),
            data=json.dumps(payload),
            content_type="application/json",
            HTTP_X_TELEGRAM_BOT_API_SECRET_TOKEN="secret-token",
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(Message.objects.filter(conversation__session_key="tg_100").count(), 2)
        mock_send.assert_called_once()


class TelegramPathNormalizationTests(TestCase):
    def test_webhook_path_normalized(self) -> None:
        self.assertTrue(settings.TELEGRAM_WEBHOOK_PATH.startswith("/"))
        self.assertTrue(settings.TELEGRAM_WEBHOOK_PATH.endswith("/"))
