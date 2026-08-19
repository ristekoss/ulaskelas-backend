from datetime import timedelta
from unittest.mock import MagicMock, patch

from django.contrib.auth.models import User
from django.test import override_settings
from django.utils import timezone
from rest_framework.test import APITestCase

from main.integrations.slcm_autofill import (
    configure_mobile_chrome,
    hash_popup_token,
    position_mobile_window,
)
from main.models import Course, CourseSemester, Profile, SLCMAutofillSession


@override_settings(
    SLCM_IRS_URL="https://slcm.ui.ac.id/student/irs",
    SLCM_BROWSER_PUBLIC_URL="https://browser.example.test",
    SLCM_AUTOFILL_TIMEOUT_SECONDS=300,
    SLCM_BROWSER_SCREEN_WIDTH=430,
    SLCM_BROWSER_SCREEN_HEIGHT=932,
)
class SLCMAutofillAPITest(APITestCase):
    def setUp(self):
        self.auth_user = User.objects.create_user(username="test-user")
        self.profile = Profile.objects.create(
            user=self.auth_user, username="test-user", name="Test User",
            npm="2200000000", faculty="Fakultas A", study_program="Program A",
            educational_program="S1 Reguler", role="student", org_code="01",
        )
        self.client.force_authenticate(self.auth_user)

    @patch("main.views_slcm_autofill.start_scraper")
    def test_create_session_returns_popup_and_rejects_second_active_session(self, start_scraper):
        result = self.client.post(
            "/api/slcm-autofill/sessions", {"given_semester": "1"}, format="json"
        )
        self.assertEqual(result.status_code, 201)
        self.assertEqual(result.data["data"]["status"], "waiting_login")
        self.assertTrue(result.data["data"]["popup_url"].startswith("https://"))
        self.assertIn("/api/slcm-autofill/popup/", result.data["data"]["popup_url"])
        duplicate = self.client.post(
            "/api/slcm-autofill/sessions", {"given_semester": "2"}, format="json"
        )
        self.assertEqual(duplicate.status_code, 409)
        self.assertEqual(duplicate.data["error"]["code"], "SESSION_ALREADY_ACTIVE")

    @patch("main.views_slcm_autofill.start_scraper")
    def test_status_is_owner_only_and_cancel_marks_session(self, _start_scraper):
        created = self.client.post(
            "/api/slcm-autofill/sessions", {"given_semester": "1"}, format="json"
        )
        session_id = created.data["data"]["session_id"]
        cancelled = self.client.delete("/api/slcm-autofill/sessions/{}".format(session_id))
        self.assertEqual(cancelled.status_code, 204)
        self.assertEqual(SLCMAutofillSession.objects.get(pk=session_id).status, "cancelled")
        other_user = User.objects.create_user(username="other")
        Profile.objects.create(
            user=other_user, username="other", name="Other", npm="2300000000",
            faculty="F", study_program="P", educational_program="S1",
            role="student", org_code="02",
        )
        self.client.force_authenticate(other_user)
        self.assertEqual(
            self.client.get("/api/slcm-autofill/sessions/{}".format(session_id)).status_code,
            404,
        )

    def test_confirm_imports_preview_and_is_idempotent(self):
        course = Course.objects.create(
            code="CSGE601020", curriculum="2024", name="Dasar Pemrograman", sks=4, term=1
        )
        session = SLCMAutofillSession.objects.create(
            user=self.profile, given_semester="1", status=SLCMAutofillSession.Status.READY,
            popup_token_hash=hash_popup_token("confirm-token"),
            expires_at=timezone.now() + timedelta(minutes=5), source_period="2025/2026 Ganjil",
            preview={"matched": [{"id": course.id, "code": course.code, "name": course.name, "sks": 4}], "duplicates": [], "unmatched": []},
        )
        url = "/api/slcm-autofill/sessions/{}/confirm".format(session.id)
        first = self.client.post(url, {}, format="json")
        second = self.client.post(url, {}, format="json")
        self.assertEqual(first.status_code, 200)
        self.assertEqual(first.data["data"]["result"]["inserted"], 1)
        self.assertEqual(second.status_code, 200)
        self.assertEqual(CourseSemester.objects.count(), 1)

    def test_expired_session_is_not_returned_as_active(self):
        session = SLCMAutofillSession.objects.create(
            user=self.profile, given_semester="1",
            popup_token_hash=hash_popup_token("expired-token"),
            expires_at=timezone.now() - timedelta(seconds=1),
        )
        result = self.client.get("/api/slcm-autofill/sessions/{}".format(session.id))
        self.assertEqual(result.status_code, 200)
        self.assertEqual(result.data["data"]["status"], "expired")

    def test_popup_token_is_single_use(self):
        token = "single-use-token"
        SLCMAutofillSession.objects.create(
            user=self.profile, given_semester="1", popup_token_hash=hash_popup_token(token),
            expires_at=timezone.now() + timedelta(minutes=5),
        )
        self.client.force_authenticate(user=None)
        url = "/api/slcm-autofill/popup/{}".format(token)
        opened = self.client.get(url)
        self.assertEqual(opened.status_code, 302)
        self.assertEqual(
            opened["Location"],
            "https://browser.example.test/?autoconnect=1&resize=scale&show_dot=true",
        )
        self.assertEqual(self.client.get(url).status_code, 404)

    def test_chrome_uses_mobile_viewport_and_touch_metrics(self):
        options = MagicMock()

        configured = configure_mobile_chrome(options)

        self.assertIs(configured, options)
        options.add_argument.assert_any_call("--window-size=430,932")
        options.add_argument.assert_any_call("--force-device-scale-factor=1")
        options.add_argument.assert_any_call("--kiosk")
        options.add_experimental_option.assert_called_once_with(
            "mobileEmulation",
            {
                "deviceMetrics": {
                    "width": 430,
                    "height": 932,
                    "pixelRatio": 1,
                    "touch": True,
                    "mobile": True,
                }
            },
        )

    def test_chrome_window_fills_the_mobile_virtual_desktop(self):
        driver = MagicMock()

        position_mobile_window(driver)

        driver.set_window_rect.assert_called_once_with(
            x=0, y=0, width=430, height=932
        )

    @override_settings(
        SLCM_BROWSER_SCREEN_WIDTH=200,
        SLCM_BROWSER_SCREEN_HEIGHT=300,
    )
    def test_chrome_enforces_minimum_usable_mobile_viewport(self):
        options = MagicMock()
        driver = MagicMock()

        configure_mobile_chrome(options)
        position_mobile_window(driver)

        options.add_argument.assert_any_call("--window-size=320,568")
        driver.set_window_rect.assert_called_once_with(
            x=0, y=0, width=320, height=568
        )
