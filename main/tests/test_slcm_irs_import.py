from io import StringIO
from unittest.mock import patch

from django.contrib.auth.models import User
from django.core.management import call_command
from django.test import TestCase, override_settings

from main.integrations.slcm_irs import import_courses, resolve_courses
from main.models import (
    Calculator,
    Course,
    CourseSemester,
    Profile,
    UserCumulativeGPA,
    UserGPA,
)


@override_settings(SLCM_REQUEST_TIMEOUT_SECONDS=15, SLCM_REQUEST_RETRIES=2)
class SLCMIRSImportTest(TestCase):
    def setUp(self):
        auth_user = User.objects.create_user(username="test-user")
        self.profile = Profile.objects.create(
            user=auth_user,
            username="test-user",
            name="Test User",
            npm="2200000000",
            faculty="Fasilkom",
            study_program="Ilmu Komputer",
            educational_program="S1 Reguler",
            role="student",
            org_code="01.00.12.01",
        )
        self.course = Course.objects.create(
            code="CSGE601020",
            curriculum="2024",
            name="Dasar Pemrograman",
            sks=4,
            term=1,
        )

    def test_resolve_courses_reports_unknown_codes(self):
        resolved, unmatched = resolve_courses(
            [
                {"code": "csge 601020", "name": "Known", "credits": 4},
                {"code": "UNKNOWN001", "name": "Unknown", "credits": 3},
            ]
        )
        self.assertEqual(resolved, [self.course])
        self.assertEqual([item["code"] for item in unmatched], ["UNKNOWN001"])

    def test_import_creates_calculator_and_skips_duplicate(self):
        first = import_courses(self.profile, "1", [self.course])
        second = import_courses(self.profile, "1", [self.course])

        semester = UserGPA.objects.get(given_semester="1")
        cumulative = UserCumulativeGPA.objects.get(user=self.profile)
        self.assertEqual(first["inserted"], [self.course])
        self.assertEqual(second["duplicates"], [self.course])
        self.assertEqual(semester.total_sks, 4)
        self.assertEqual(cumulative.total_sks, 4)
        self.assertEqual(CourseSemester.objects.count(), 1)
        self.assertEqual(Calculator.objects.count(), 1)

    @patch(
        "main.integrations.slcm_irs.add_semester_gpa",
        side_effect=RuntimeError("forced failure"),
    )
    def test_import_rolls_back_all_changes(self, _add_semester_gpa):
        with self.assertRaises(RuntimeError):
            import_courses(self.profile, "1", [self.course])
        self.assertFalse(UserCumulativeGPA.objects.exists())
        self.assertFalse(UserGPA.objects.exists())
        self.assertFalse(Calculator.objects.exists())

    @patch("main.management.commands.import_slcm_irs.SLCMClient.fetch_course_plan")
    @patch("main.management.commands.import_slcm_irs.getpass.getpass", return_value="secret")
    def test_management_command_dry_run_warns_about_stale_data(self, _getpass, fetch):
        fetch.return_value = {
            "username": self.profile.username,
            "period": "2026-1",
            "warning_stale_data": True,
            "courses": [
                {"code": self.course.code, "name": self.course.name, "credits": 4}
            ],
        }
        stdout = StringIO()
        call_command(
            "import_slcm_irs",
            username=self.profile.username,
            semester="1",
            dry_run=True,
            stdout=stdout,
        )
        self.assertIn("may be stale", stdout.getvalue())
        self.assertIn("Dry run", stdout.getvalue())
        self.assertFalse(UserGPA.objects.exists())

    @patch("main.management.commands.import_slcm_irs.SLCMClient.fetch_course_plan")
    @patch("main.management.commands.import_slcm_irs.getpass.getpass", return_value="secret")
    def test_management_command_rejects_identity_mismatch(self, _getpass, fetch):
        fetch.return_value = {
            "username": "other-user",
            "period": "2026-1",
            "warning_stale_data": False,
            "courses": [],
        }
        with self.assertRaisesMessage(Exception, "does not match"):
            call_command(
                "import_slcm_irs",
                username=self.profile.username,
                semester="1",
                dry_run=True,
            )
