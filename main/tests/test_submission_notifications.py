from unittest.mock import patch

from django.contrib.auth.models import User
from django.test import TestCase, override_settings
from rest_framework.test import APIClient

from main.models import Answer, Course, Profile, Question, Review, Tag
from main.notification_email import send_submission_notification


@override_settings(
    DEFAULT_FROM_EMAIL="noreply@example.com",
    NOTIFICATION_RECIPIENT_EMAILS=["admin@example.com"],
)
class SubmissionNotificationViewTest(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.user = User.objects.create_user(username="tester")
        self.profile = Profile.objects.create(
            user=self.user,
            username="tester",
            name="Tester",
            npm="2106700000",
            faculty="Fasilkom",
            study_program="Ilmu Komputer",
            educational_program="S1 Reguler",
            role="MAHASISWA",
            org_code="CS",
        )
        self.course = Course.objects.create(
            code="CSGE601021",
            curriculum="2020",
            name="Testing Course",
            description="",
            sks=3,
            term=1,
            prerequisites="",
        )
        self.tag = Tag.objects.create(tag_name="MENARIK")
        self.client.force_authenticate(user=self.user)

    @patch("main.notification_email.send_mail")
    def test_tanya_teman_post_sends_notification_email(self, mock_send_mail):
        response = self.client.post(
            "/api/tanya-teman",
            {"question_text": "Pertanyaan baru", "is_anonym": 0, "course_id": self.course.id},
            format="json",
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(Question.objects.count(), 1)
        mock_send_mail.assert_called_once()
        self.assertIn("New Question", mock_send_mail.call_args.kwargs["subject"])
        self.assertEqual(
            mock_send_mail.call_args.kwargs["recipient_list"],
            ["admin@example.com"],
        )

    @patch("main.notification_email.send_mail")
    def test_jawab_teman_post_sends_notification_email(self, mock_send_mail):
        question = Question.objects.create(
            user=self.profile,
            question_text="Pertanyaan lama",
            course=self.course,
            is_anonym=0,
            attachment=None,
        )

        response = self.client.post(
            "/api/jawab-teman",
            {"question_id": question.id, "answer_text": "Jawaban baru", "is_anonym": 0},
            format="json",
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(Answer.objects.count(), 1)
        mock_send_mail.assert_called_once()
        self.assertIn("New Answer", mock_send_mail.call_args.kwargs["subject"])

    @patch("main.serializers.get_config", return_value={})
    @patch("main.notification_email.send_mail")
    def test_review_post_sends_notification_email(self, mock_send_mail, _mock_get_config):
        response = self.client.post(
            "/api/reviews",
            {
                "course_code": self.course.code,
                "academic_year": "2024/2025",
                "semester": 1,
                "content": "Review baru",
                "is_anonym": False,
                "tags": [self.tag.tag_name],
            },
            format="json",
        )

        self.assertEqual(response.status_code, 201)
        self.assertEqual(Review.objects.count(), 1)
        mock_send_mail.assert_called_once()
        self.assertIn("New Review", mock_send_mail.call_args.kwargs["subject"])

    @patch("main.notification_email.send_mail", side_effect=Exception("smtp down"))
    def test_tanya_teman_post_stays_successful_when_email_fails(self, _mock_send_mail):
        with self.assertLogs("main.notification_email", level="ERROR") as log_context:
            response = self.client.post(
                "/api/tanya-teman",
                {"question_text": "Pertanyaan baru", "is_anonym": 0},
                format="json",
            )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(Question.objects.count(), 1)
        self.assertIn("Failed to send submission notification", "\n".join(log_context.output))


class SubmissionNotificationHelperTest(TestCase):
    @override_settings(
        DEFAULT_FROM_EMAIL="noreply@example.com",
        NOTIFICATION_RECIPIENT_EMAILS=[],
    )
    def test_logs_warning_when_recipient_list_is_empty(self):
        with self.assertLogs("main.notification_email", level="WARNING") as log_context:
            result = send_submission_notification(
                subject="Subject",
                message="Message",
                event_type="question",
                object_id=1,
            )

        self.assertFalse(result)
        self.assertIn("recipient list is empty", "\n".join(log_context.output))
