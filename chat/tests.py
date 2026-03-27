from unittest.mock import patch

from django.test import TestCase
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
