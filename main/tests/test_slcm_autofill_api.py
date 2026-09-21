from datetime import date, timedelta
from unittest.mock import patch

from django.contrib.auth.models import User
from django.test import override_settings
from django.utils import timezone
from rest_framework.test import APITestCase

from main.integrations.slcm_autofill import _fetch_session
from main.models import Course, CourseSemester, Profile, SLCMAutofillSession


@override_settings(
    SLCM_AUTOFILL_TIMEOUT_SECONDS=300,
    SLCM_REQUEST_TIMEOUT_SECONDS=15,
    SLCM_REQUEST_RETRIES=2,
)
class SLCMAutofillAPITest(APITestCase):
    def setUp(self):
        self.auth_user = User.objects.create_user(username="test-user")
        self.profile = Profile.objects.create(
            user=self.auth_user,
            username="test-user",
            name="Test User",
            npm="2200000000",
            faculty="Fakultas A",
            study_program="Program A",
            educational_program="S1 Reguler",
            role="student",
            org_code="01",
        )
        self.client.force_authenticate(self.auth_user)

    def _credentials(self, **extra):
        return {"username": "test-user", "password": "secret", **extra}

    @patch("main.views_slcm_autofill.start_scraper")
    def test_create_session_passes_ephemeral_credentials_to_worker(self, start_scraper):
        with patch(
            "main.views_slcm_autofill.transaction.on_commit",
            side_effect=lambda callback: callback(),
        ):
            result = self.client.post(
                "/api/slcm-autofill/sessions",
                self._credentials(given_semester="1"),
                format="json",
            )

        self.assertEqual(result.status_code, 201)
        self.assertEqual(result.data["data"]["status"], "waiting_login")
        self.assertNotIn("password", result.data["data"])
        self.assertNotIn("popup_url", result.data["data"])
        session = SLCMAutofillSession.objects.get()
        start_scraper.assert_called_once_with(session.id, "test-user", "secret")

    @patch("main.views_slcm_autofill.start_scraper")
    def test_create_session_rejects_second_active_session(self, _start_scraper):
        payload = self._credentials(given_semester="1")
        self.client.post("/api/slcm-autofill/sessions", payload, format="json")
        duplicate = self.client.post("/api/slcm-autofill/sessions", payload, format="json")
        self.assertEqual(duplicate.status_code, 409)
        self.assertEqual(duplicate.data["error"]["code"], "SESSION_ALREADY_ACTIVE")

    def test_create_session_requires_matching_credentials(self):
        missing = self.client.post(
            "/api/slcm-autofill/sessions", {"username": "test-user"}, format="json"
        )
        mismatch = self.client.post(
            "/api/slcm-autofill/sessions",
            {"username": "other", "password": "secret"},
            format="json",
        )
        self.assertEqual(missing.status_code, 400)
        self.assertEqual(missing.data["error"]["code"], "INVALID_CREDENTIALS")
        self.assertEqual(mismatch.status_code, 400)
        self.assertEqual(mismatch.data["error"]["code"], "IDENTITY_MISMATCH")

    @patch("main.views_slcm_autofill.timezone.localdate", return_value=date(2026, 8, 24))
    @patch("main.views_slcm_autofill.start_scraper")
    def test_create_session_defaults_to_current_semester(self, _start, _localdate):
        result = self.client.post(
            "/api/slcm-autofill/sessions", self._credentials(), format="json"
        )
        self.assertEqual(result.status_code, 201)
        self.assertEqual(result.data["data"]["given_semester"], "9")

    @patch("main.integrations.slcm_autofill.SLCMClient.fetch_course_plan")
    def test_worker_builds_preview_and_preserves_stale_warning(self, fetch):
        course = Course.objects.create(
            code="CSGE601020",
            curriculum="2024",
            name="Dasar Pemrograman",
            sks=4,
            term=1,
        )
        fetch.return_value = {
            "username": "test-user",
            "period": "2026-1",
            "warning_stale_data": True,
            "courses": [
                {"code": course.code, "name": course.name, "credits": 4}
            ],
        }
        session = SLCMAutofillSession.objects.create(
            user=self.profile,
            given_semester="1",
            expires_at=timezone.now() + timedelta(minutes=5),
        )

        _fetch_session(session.id, "test-user", "secret")

        session.refresh_from_db()
        self.assertEqual(session.status, SLCMAutofillSession.Status.READY)
        self.assertTrue(session.preview["warning_stale_data"])
        self.assertEqual(session.preview["matched"][0]["code"], course.code)

    @patch("main.integrations.slcm_autofill.SLCMClient.fetch_course_plan")
    def test_worker_rejects_authenticated_identity_mismatch(self, fetch):
        fetch.return_value = {
            "username": "other-user",
            "period": "2026-1",
            "warning_stale_data": False,
            "courses": [],
        }
        session = SLCMAutofillSession.objects.create(
            user=self.profile,
            given_semester="1",
            expires_at=timezone.now() + timedelta(minutes=5),
        )
        _fetch_session(session.id, "test-user", "secret")
        session.refresh_from_db()
        self.assertEqual(session.status, SLCMAutofillSession.Status.FAILED)
        self.assertEqual(session.error["code"], "IDENTITY_MISMATCH")

    def test_confirm_imports_preview_and_is_idempotent(self):
        course = Course.objects.create(
            code="CSGE601020", curriculum="2024", name="Dasar Pemrograman", sks=4, term=1
        )
        session = SLCMAutofillSession.objects.create(
            user=self.profile,
            given_semester="1",
            status=SLCMAutofillSession.Status.READY,
            expires_at=timezone.now() + timedelta(minutes=5),
            source_period="2026-1",
            preview={
                "matched": [{"id": course.id, "code": course.code, "name": course.name, "sks": 4}],
                "duplicates": [],
                "unmatched": [],
                "warning_stale_data": False,
            },
        )
        url = "/api/slcm-autofill/sessions/{}/confirm".format(session.id)
        first = self.client.post(url, {}, format="json")
        second = self.client.post(url, {}, format="json")
        self.assertEqual(first.status_code, 200)
        self.assertEqual(second.status_code, 200)
        self.assertEqual(CourseSemester.objects.count(), 1)

    def test_expired_session_is_marked_expired(self):
        session = SLCMAutofillSession.objects.create(
            user=self.profile,
            given_semester="1",
            expires_at=timezone.now() - timedelta(seconds=1),
        )
        result = self.client.get("/api/slcm-autofill/sessions/{}".format(session.id))
        self.assertEqual(result.data["data"]["status"], "expired")
