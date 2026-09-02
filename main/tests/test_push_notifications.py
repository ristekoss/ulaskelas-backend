from django.contrib.auth.models import User
from django.core.management import call_command
from django.test import TestCase, override_settings
from rest_framework.test import APIClient

from main.models import Calculator, Course, DeviceToken, Notification, Profile, Review
from main.push_notifications import remind_course_review_after_grade_edit


@override_settings(FIREBASE_ENABLED=False)
class PushNotificationTest(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username="notified")
        self.profile = Profile.objects.create(
            user=self.user, username="notified", name="Notified", npm="2106700000",
            faculty="Fasilkom", study_program="Ilmu Komputer",
            educational_program="S1 Reguler", role="MAHASISWA", org_code="CS",
        )
        self.course = Course.objects.create(
            code="CSGE600001", curriculum="2020", name="Course", description="",
            sks=3, term=1, prerequisites="",
        )
        self.calculator = Calculator.objects.create(user=self.profile, course=self.course)
        self.client = APIClient()
        self.client.force_authenticate(user=self.user)

    def test_device_registration_moves_existing_token_and_unregisters(self):
        other_user = User.objects.create_user(username="other")
        other = Profile.objects.create(
            user=other_user, username="other", name="Other", npm="2106700001",
            faculty="Fasilkom", study_program="Ilmu Komputer",
            educational_program="S1 Reguler", role="MAHASISWA", org_code="CS",
        )
        DeviceToken.objects.create(user=other, token="device", platform="android")

        result = self.client.post(
            "/api/device-tokens",
            {"token": "device", "platform": "ios"},
            format="json",
        )
        self.assertEqual(result.status_code, 200)
        device = DeviceToken.objects.get(token="device")
        self.assertEqual(
            (device.user, device.platform, device.is_active),
            (self.profile, "ios", True),
        )

        result = self.client.delete("/api/device-tokens", {"token": "device"}, format="json")
        self.assertEqual(result.status_code, 204)
        device.refresh_from_db()
        self.assertFalse(device.is_active)

    def test_inbox_read_and_read_all_are_user_scoped(self):
        first = Notification.objects.create(
            user=self.profile, type=Notification.Type.CALCULATOR_REMINDER,
            title="Reminder", body="Body", target=Notification.Target.GRADE_CALCULATOR,
            dedupe_key="one",
        )
        Notification.objects.create(
            user=self.profile, type=Notification.Type.COURSE_REVIEW_REMINDER,
            title="Reminder", body="Body", target=Notification.Target.COURSE_REVIEW,
            dedupe_key="two",
        )
        result = self.client.get("/api/notifications")
        self.assertEqual(result.data["data"]["unread_count"], 2)

        result = self.client.post("/api/notifications/{}/read".format(first.id))
        self.assertEqual(result.data["data"]["unread_count"], 1)
        result = self.client.post("/api/notifications/read-all")
        self.assertEqual(result.data["data"]["unread_count"], 0)

    def test_grade_edit_reminder_is_deduplicated_and_skips_reviewed_course(self):
        remind_course_review_after_grade_edit(self.calculator)
        remind_course_review_after_grade_edit(self.calculator)
        self.assertEqual(Notification.objects.count(), 1)
        Notification.objects.all().delete()
        Review.objects.create(
            user=self.profile, course=self.course, academic_year="2025/2026", semester=1,
            content="Reviewed", is_anonym=False,
        )
        remind_course_review_after_grade_edit(self.calculator)
        self.assertEqual(Notification.objects.count(), 0)

    def test_calculator_command_is_idempotent_per_iso_week(self):
        call_command("send_notification_reminders", type="calculator", date="2026-08-28")
        call_command("send_notification_reminders", type="calculator", date="2026-08-28")
        self.assertEqual(Notification.objects.count(), 1)

    def test_monthly_command_only_runs_on_real_last_day(self):
        call_command("send_notification_reminders", type="review", date="2028-02-28")
        self.assertEqual(Notification.objects.count(), 0)
        call_command("send_notification_reminders", type="review", date="2028-02-29")
        self.assertEqual(Notification.objects.count(), 1)
