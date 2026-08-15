from io import StringIO
from unittest.mock import Mock, patch

import requests
from django.contrib.auth.models import User
from django.core.management import call_command, CommandError
from django.test import TestCase
from rest_framework.test import APITestCase

from courseUpdater.courseApi import (
    CourseCatalogUnavailable,
    CourseSyncError,
    _apply_courses_payload,
    _fetch_courses_json,
)
from main.models import Course, Profile, Review, StudyProgram, StudyProgramCourse


class CourseSyncTest(TestCase):
    def setUp(self):
        self.program = StudyProgram.objects.create(
            org_code="01",
            faculty="Fakultas A",
            study_program="Program A",
            educational_program="S1 Reguler",
        )

    @patch(
        "courseUpdater.courseApi.get_config",
        return_value={"PZ": "Wajib Fakultas"},
    )
    def test_sync_stores_program_specific_metadata(self, _get_config):
        result = _apply_courses_payload(
            self.program,
            {
                "courses": [
                    {
                        "code": "PZ000001",
                        "curriculum": "2024",
                        "credit": "3",
                        "description": None,
                        "name": "Course A",
                        "term": "2",
                        "prerequisite": None,
                    },
                    {
                        "code": "XX000001",
                        "curriculum": "2024",
                        "credit": "2",
                        "description": "",
                        "name": "Course B",
                        "term": "1",
                        "prerequisite": "",
                    },
                ]
            },
        )

        self.assertEqual(result["active_courses"], 2)
        mandatory = StudyProgramCourse.objects.get(course__code="PZ000001")
        unknown = StudyProgramCourse.objects.get(course__code="XX000001")
        self.assertEqual(mandatory.program_term, 2)
        self.assertEqual(mandatory.course_type, "MANDATORY")
        self.assertEqual(unknown.course_type, "UNKNOWN")
        self.program.refresh_from_db()
        self.assertIsNotNone(self.program.last_synced_at)

    @patch("courseUpdater.courseApi.get_config", return_value={})
    def test_successful_sync_marks_missing_relations_inactive(self, _get_config):
        old_course = Course.objects.create(
            code="OLD00001", curriculum="2024", name="Old", sks=3, term=1
        )
        mapping = StudyProgramCourse.objects.create(
            study_program=self.program,
            course=old_course,
            program_term=1,
        )

        _apply_courses_payload(self.program, {"courses": []})

        mapping.refresh_from_db()
        self.assertFalse(mapping.is_active)

    @patch("courseUpdater.courseApi.get_config", return_value={})
    def test_sync_reactivates_course_that_returns_to_catalog(self, _get_config):
        course = Course.objects.create(
            code="BACK0001", curriculum="2024", name="Old name", sks=3, term=1
        )
        mapping = StudyProgramCourse.objects.create(
            study_program=self.program,
            course=course,
            program_term=1,
            is_active=False,
        )

        _apply_courses_payload(
            self.program,
            {
                "courses": [
                    {
                        "code": "BACK0001",
                        "curriculum": "2025",
                        "credit": "4",
                        "name": "New name",
                        "term": "2",
                    }
                ]
            },
        )

        mapping.refresh_from_db()
        course.refresh_from_db()
        self.assertTrue(mapping.is_active)
        self.assertEqual(mapping.program_term, 2)
        self.assertEqual(course.name, "New name")
        self.assertEqual(Course.objects.filter(code="BACK0001").count(), 1)

    @patch("courseUpdater.courseApi.get_config", return_value={})
    def test_deactivation_preserves_course_and_review_history(self, _get_config):
        course = Course.objects.create(
            code="HIST0001", curriculum="2024", name="History", sks=3, term=1
        )
        mapping = StudyProgramCourse.objects.create(
            study_program=self.program,
            course=course,
            program_term=1,
        )
        review = Review.objects.create(
            course=course,
            academic_year="2024/2025",
            semester=Review.Semester.GANJIL,
            content="Historical review",
            hate_speech_status=Review.HateSpeechStatus.APPROVED,
        )

        _apply_courses_payload(self.program, {"courses": []})

        mapping.refresh_from_db()
        self.assertFalse(mapping.is_active)
        self.assertTrue(Course.objects.filter(pk=course.pk).exists())
        self.assertTrue(Review.objects.filter(pk=review.pk, course=course).exists())

    def test_invalid_payload_does_not_change_existing_relations(self):
        course = Course.objects.create(
            code="OLD00001", curriculum="2024", name="Old", sks=3, term=1
        )
        mapping = StudyProgramCourse.objects.create(
            study_program=self.program,
            course=course,
            program_term=1,
        )

        with self.assertRaises(CourseSyncError):
            _apply_courses_payload(self.program, {"unexpected": []})

        mapping.refresh_from_db()
        self.assertTrue(mapping.is_active)

    @patch("courseUpdater.courseApi.get_config", return_value={})
    def test_partially_invalid_sync_does_not_deactivate_old_relations(
        self, _get_config
    ):
        old_course = Course.objects.create(
            code="OLD00001", curriculum="2024", name="Old", sks=3, term=1
        )
        mapping = StudyProgramCourse.objects.create(
            study_program=self.program,
            course=old_course,
            program_term=1,
        )

        result = _apply_courses_payload(
            self.program,
            {
                "courses": [
                    {
                        "code": "NEW00001",
                        "curriculum": "2024",
                        "credit": "3",
                        "name": "New",
                        "term": "1",
                    },
                    {"code": "BROKEN"},
                ]
            },
        )

        mapping.refresh_from_db()
        self.assertTrue(mapping.is_active)
        self.assertEqual(result["skipped_courses"], 1)
        self.assertEqual(result["inactive_courses"], 0)

    @patch("courseUpdater.courseApi.get_config", return_value={})
    def test_sync_rejects_invalid_course_code_sentinels(self, _get_config):
        result = _apply_courses_payload(
            self.program,
            {
                "courses": [
                    {"code": None},
                    {"code": ""},
                    {"code": "   "},
                    {"code": "None"},
                    {"code": "NULL"},
                    {"code": "n/a"},
                    {"name": "Missing code"},
                    {
                        "code": " CUSTOM-1 ",
                        "curriculum": "2024",
                        "credit": "3",
                        "name": "Valid custom code",
                        "term": "1",
                    },
                ]
            },
        )

        self.assertEqual(result["active_courses"], 1)
        self.assertEqual(result["skipped_courses"], 7)
        self.assertEqual(
            list(Course.objects.values_list("code", flat=True)),
            ["CUSTOM-1"],
        )

    @patch("courseUpdater.courseApi.requests.get")
    def test_empty_object_response_means_catalog_unavailable(self, mock_get):
        mock_get.return_value.json.return_value = {}

        with self.assertRaises(CourseCatalogUnavailable):
            _fetch_courses_json("https://sunjad.test/catalog")

        mock_get.return_value.raise_for_status.assert_called_once_with()

    @patch("courseUpdater.courseApi.time.sleep")
    @patch("courseUpdater.courseApi.requests.get")
    def test_transient_fetch_failure_is_retried(self, mock_get, mock_sleep):
        successful_response = Mock()
        successful_response.json.return_value = {"courses": []}
        mock_get.side_effect = [
            requests.ConnectionError("SunJad is temporarily unavailable"),
            successful_response,
        ]

        payload = _fetch_courses_json("https://sunjad.test/catalog")

        self.assertEqual(payload, {"courses": []})
        self.assertEqual(mock_get.call_count, 2)
        mock_sleep.assert_called_once_with(1)

    @patch("courseUpdater.courseApi.time.sleep")
    @patch("courseUpdater.courseApi.requests.get")
    def test_exhausted_retries_raise_sync_error(self, mock_get, mock_sleep):
        mock_get.side_effect = requests.Timeout("SunJad timed out")

        with self.assertRaises(CourseSyncError):
            _fetch_courses_json("https://sunjad.test/catalog")

        self.assertEqual(mock_get.call_count, 3)
        self.assertEqual(
            [call.args[0] for call in mock_sleep.call_args_list],
            [1, 2],
        )


class SyncCoursesCommandTest(TestCase):
    @patch(
        "main.management.commands.sync_courses.get_supported_program_configs",
        return_value={"01": {}, "02": {}},
    )
    @patch("main.management.commands.sync_courses.update_courses")
    def test_unavailable_catalog_does_not_fail_command(
        self, mock_update, _mock_configs
    ):
        mock_update.side_effect = [
            CourseCatalogUnavailable("catalog unavailable"),
            {
                "org_code": "02",
                "active_courses": 1,
                "inactive_courses": 0,
                "skipped_courses": 0,
            },
        ]
        stderr = StringIO()

        call_command("sync_courses", "--all", stderr=stderr)

        self.assertIn(
            "Course catalog unavailable for 1 program(s): 01",
            stderr.getvalue(),
        )

    @patch(
        "main.management.commands.sync_courses.get_supported_program_configs",
        return_value={"01": {}},
    )
    @patch("main.management.commands.sync_courses.update_courses")
    def test_technical_failure_still_fails_command(self, mock_update, _mock_configs):
        mock_update.side_effect = CourseSyncError("invalid response")

        with self.assertRaisesMessage(CommandError, "Synchronization failed for 1"):
            call_command("sync_courses", "--all", stderr=StringIO())


class RefreshCoursesTest(APITestCase):
    def setUp(self):
        self.auth_user = User.objects.create_user(username="test-user")
        Profile.objects.create(
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

    @patch(
        "main.views.courseApi.update_courses",
        side_effect=CourseCatalogUnavailable("SunJad course catalog is unavailable"),
    )
    def test_unavailable_catalog_returns_conflict(self, _mock_update):
        response = self.client.post("/update-course/")

        self.assertEqual(response.status_code, 409)
        self.assertEqual(
            response.data["error"]["code"],
            "COURSE_CATALOG_UNAVAILABLE",
        )
