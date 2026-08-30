from unittest.mock import patch

from django.contrib.auth.models import User
from django.test import TestCase, override_settings
from rest_framework.test import APIClient

from main.models import Answer, Course, Profile, Question, Review, Tag
from main.notification_email import send_submission_notification


@override_settings(
    DEFAULT_FROM_EMAIL="noreply@example.com",
    NOTIFICATION_RECIPIENT_EMAILS=["admin@example.com"],
    MODERATION_TRIGGER_WORDS=("kata kasar",),
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

    @patch("main.notification_email.send_notification_email")
    def test_tanya_teman_post_sends_notification_email(self, mock_send_notification_email):
        response = self.client.post(
            "/api/tanya-teman",
            {"question_text": "Pertanyaan baru", "is_anonym": 0, "course_id": self.course.id},
            format="json",
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(Question.objects.count(), 1)
        self.assertEqual(
            Question.objects.get().verification_status,
            Question.VerificationStatus.APPROVED,
        )
        self.assertEqual(response.data["data"]["moderation_status"], "APPROVED")
        mock_send_notification_email.assert_called_once()
        self.assertIn(
            "New Question", mock_send_notification_email.call_args.kwargs["subject"]
        )

    @patch("main.notification_email.send_notification_email")
    def test_jawab_teman_post_sends_notification_email(self, mock_send_notification_email):
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
        self.assertEqual(
            Answer.objects.get().verification_status,
            Answer.VerificationStatus.APPROVED,
        )
        self.assertEqual(response.data["data"]["moderation_status"], "APPROVED")
        mock_send_notification_email.assert_called_once()
        self.assertIn(
            "New Answer", mock_send_notification_email.call_args.kwargs["subject"]
        )

    @patch("main.serializers.get_config", return_value={})
    @patch("main.notification_email.send_notification_email")
    def test_review_post_sends_notification_email(
        self, mock_send_notification_email, _mock_get_config
    ):
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
        self.assertEqual(
            Review.objects.get().hate_speech_status,
            Review.HateSpeechStatus.APPROVED,
        )
        self.assertEqual(response.data["data"]["moderation_status"], "APPROVED")
        mock_send_notification_email.assert_called_once()
        self.assertEqual(
            mock_send_notification_email.call_args.kwargs["subject"],
            "TemanKuliah — Review Baru: Testing Course",
        )

    @patch("main.notification_email.send_notification_email")
    def test_detected_question_waits_and_uses_detected_subject(
        self, mock_send_notification_email
    ):
        response = self.client.post(
            "/api/tanya-teman",
            {"question_text": "Ini kata-kasar", "is_anonym": 0},
            format="json",
        )

        question = Question.objects.get()
        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            question.verification_status, Question.VerificationStatus.WAITING
        )
        self.assertEqual(response.data["data"]["moderation_status"], "WAITING")
        self.assertTrue(
            mock_send_notification_email.call_args.kwargs["subject"].startswith(
                "[DETECTED] "
            )
        )

    @patch("main.notification_email.send_notification_email")
    def test_detected_answer_waits_and_uses_detected_subject(
        self, mock_send_notification_email
    ):
        question = Question.objects.create(
            user=self.profile,
            question_text="Pertanyaan lama",
            course=self.course,
            is_anonym=0,
            verification_status=Question.VerificationStatus.APPROVED,
        )

        response = self.client.post(
            "/api/jawab-teman",
            {
                "question_id": question.id,
                "answer_text": "Jawaban kata kasar",
                "is_anonym": 0,
            },
            format="json",
        )

        answer = Answer.objects.get()
        self.assertEqual(response.status_code, 200)
        self.assertEqual(answer.verification_status, Answer.VerificationStatus.WAITING)
        self.assertEqual(response.data["data"]["moderation_status"], "WAITING")
        self.assertTrue(
            mock_send_notification_email.call_args.kwargs["subject"].startswith(
                "[DETECTED] "
            )
        )

    @patch("main.serializers.get_config", return_value={})
    @patch("main.notification_email.send_notification_email")
    def test_detected_review_waits_and_is_hidden_from_other_users(
        self, mock_send_notification_email, _mock_get_config
    ):
        response = self.client.post(
            "/api/reviews",
            {
                "course_code": self.course.code,
                "academic_year": "2024/2025",
                "semester": 1,
                "content": "Review kata kasar",
                "is_anonym": False,
                "tags": [self.tag.tag_name],
            },
            format="json",
        )

        review = Review.objects.get()
        self.assertEqual(response.status_code, 201)
        self.assertEqual(review.hate_speech_status, Review.HateSpeechStatus.WAITING)
        self.assertEqual(response.data["data"]["moderation_status"], "WAITING")
        self.assertEqual(
            mock_send_notification_email.call_args.kwargs["subject"],
            "[DETECTED] TemanKuliah — Review Baru: Testing Course",
        )

        other_user = User.objects.create_user(username="other")
        Profile.objects.create(
            user=other_user,
            username="other",
            name="Other",
            npm="2206700000",
            faculty="Fasilkom",
            study_program="Ilmu Komputer",
            educational_program="S1 Reguler",
            role="MAHASISWA",
            org_code="CS",
        )
        self.client.force_authenticate(user=other_user)
        hidden_response = self.client.get(f"/api/reviews?id={review.id}")
        self.assertEqual(hidden_response.status_code, 404)

    @patch("main.serializers.get_config", return_value={})
    @patch("main.notification_email.send_notification_email")
    def test_review_edit_is_rescanned(
        self, mock_send_notification_email, _mock_get_config
    ):
        review = Review.objects.create(
            user=self.profile,
            course=self.course,
            academic_year="2024/2025",
            semester=1,
            content="Review bersih",
            hate_speech_status=Review.HateSpeechStatus.APPROVED,
        )

        response = self.client.put(
            "/api/reviews",
            {"review_id": review.id, "content": "Edit kata kasar"},
            format="json",
        )

        review.refresh_from_db()
        self.assertEqual(response.status_code, 201)
        self.assertEqual(review.hate_speech_status, Review.HateSpeechStatus.WAITING)
        self.assertEqual(response.data["data"]["moderation_status"], "WAITING")
        self.assertEqual(
            mock_send_notification_email.call_args.kwargs["subject"],
            "[DETECTED] TemanKuliah — Review Baru: Testing Course",
        )

        mock_send_notification_email.reset_mock()
        clean_response = self.client.put(
            "/api/reviews",
            {"review_id": review.id, "content": "Edit sudah bersih"},
            format="json",
        )

        review.refresh_from_db()
        self.assertEqual(clean_response.status_code, 201)
        self.assertEqual(review.hate_speech_status, Review.HateSpeechStatus.APPROVED)
        self.assertEqual(
            clean_response.data["data"]["moderation_status"], "APPROVED"
        )
        mock_send_notification_email.assert_not_called()

    @patch(
        "main.notification_email.send_notification_email",
        side_effect=Exception("mailer down"),
    )
    def test_tanya_teman_post_stays_successful_when_email_fails(
        self, _mock_send_notification_email
    ):
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
