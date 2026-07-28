from io import StringIO
from unittest.mock import patch

from django.contrib.auth.models import User
from django.core.management import call_command
from django.test import TestCase

from main.integrations.siak_irs import (
    IRSParseError,
    import_courses,
    parse_irs_tables,
    resolve_courses,
)
from main.models import (
    Calculator,
    Course,
    CourseSemester,
    Profile,
    UserCumulativeGPA,
    UserGPA,
)


class SIAKIRSParserTest(TestCase):
    def test_parser_recognizes_irs_headers_and_deduplicates_codes(self):
        courses = parse_irs_tables(
            [
                {
                    "headers": ["No.", "Kode MK", "Nama Mata Kuliah", "SKS"],
                    "rows": [
                        ["1", " csge 601020 ", "Dasar Pemrograman", "4 SKS"],
                        ["2", "CSGE601020", "Dasar Pemrograman", "4"],
                        ["3", "UIGE600001", "MPKT", "5"],
                    ],
                }
            ]
        )

        self.assertEqual(
            courses,
            [
                {
                    "code": "CSGE601020",
                    "name": "Dasar Pemrograman",
                    "credits": 4,
                },
                {"code": "UIGE600001", "name": "MPKT", "credits": 5},
            ],
        )

    def test_parser_selects_largest_matching_table(self):
        courses = parse_irs_tables(
            [
                {
                    "headers": ["Course Code", "Course Name", "Credits"],
                    "rows": [["OLD000001", "Old", "2"]],
                },
                {
                    "headers": ["Kode", "Mata Kuliah", "Jumlah SKS"],
                    "rows": [
                        ["NEW000001", "New A", "3"],
                        ["NEW000002", "New B", "2"],
                    ],
                },
            ]
        )

        self.assertEqual(
            [course["code"] for course in courses],
            ["NEW000001", "NEW000002"],
        )

    def test_parser_ignores_larger_matching_table_without_valid_courses(self):
        courses = parse_irs_tables(
            [
                {
                    "headers": ["Kode MK", "Nama Mata Kuliah", "SKS"],
                    "rows": [
                        ["", "Summary row", ""],
                        ["", "Another summary row", ""],
                        ["", "Total", "5"],
                    ],
                },
                {
                    "headers": ["Kode", "Mata Kuliah", "Jumlah SKS"],
                    "rows": [["VALID0001", "Valid Course", "3"]],
                },
            ]
        )

        self.assertEqual(
            courses,
            [{"code": "VALID0001", "name": "Valid Course", "credits": 3}],
        )

    def test_parser_rejects_unrecognized_page(self):
        with self.assertRaises(IRSParseError):
            parse_irs_tables(
                [{"headers": ["Tanggal", "Keterangan"], "rows": [["1", "Test"]]}]
            )


class SIAKIRSImportTest(TestCase):
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
                {"code": "csge601020", "name": "Known", "credits": 4},
                {"code": "UNKNOWN001", "name": "Unknown", "credits": 3},
            ]
        )

        self.assertEqual(resolved, [self.course])
        self.assertEqual([course["code"] for course in unmatched], ["UNKNOWN001"])

    def test_import_creates_semester_calculator_and_updates_credits(self):
        result = import_courses(self.profile, "1", [self.course])

        semester = UserGPA.objects.get(given_semester="1")
        cumulative = UserCumulativeGPA.objects.get(user=self.profile)
        self.assertTrue(result["semester_created"])
        self.assertEqual(result["inserted"], [self.course])
        self.assertEqual(semester.total_sks, 4)
        self.assertEqual(cumulative.total_sks, 4)
        self.assertTrue(
            CourseSemester.objects.filter(
                semester=semester, course=self.course
            ).exists()
        )
        self.assertTrue(
            Calculator.objects.filter(user=self.profile, course=self.course).exists()
        )

    def test_import_skips_existing_course_without_replacing_calculator(self):
        first_result = import_courses(self.profile, "1", [self.course])
        calculator_id = CourseSemester.objects.get(course=self.course).calculator_id

        second_result = import_courses(self.profile, "1", [self.course])

        semester = UserGPA.objects.get(given_semester="1")
        cumulative = UserCumulativeGPA.objects.get(user=self.profile)
        self.assertEqual(second_result["inserted"], [])
        self.assertEqual(second_result["duplicates"], [self.course])
        self.assertEqual(semester.total_sks, 4)
        self.assertEqual(cumulative.total_sks, 4)
        self.assertEqual(
            CourseSemester.objects.get(course=self.course).calculator_id,
            calculator_id,
        )
        self.assertEqual(Calculator.objects.count(), 1)
        self.assertEqual(first_result["inserted"], [self.course])

    @patch(
        "main.integrations.siak_irs.add_semester_gpa",
        side_effect=RuntimeError("forced failure"),
    )
    def test_import_rolls_back_all_changes(self, _add_semester_gpa):
        with self.assertRaises(RuntimeError):
            import_courses(self.profile, "1", [self.course])

        self.assertFalse(UserCumulativeGPA.objects.exists())
        self.assertFalse(UserGPA.objects.exists())
        self.assertFalse(Calculator.objects.exists())
        self.assertFalse(CourseSemester.objects.exists())

    @patch(
        "main.management.commands.import_siak_irs.Command._scrape",
        return_value=[
            {
                "code": "CSGE601020",
                "name": "Dasar Pemrograman",
                "credits": 4,
            }
        ],
    )
    def test_management_command_dry_run_does_not_write(self, _scrape):
        stdout = StringIO()

        call_command(
            "import_siak_irs",
            username=self.profile.username,
            semester="1",
            dry_run=True,
            stdout=stdout,
        )

        self.assertIn("Dry run", stdout.getvalue())
        self.assertFalse(UserCumulativeGPA.objects.exists())
        self.assertFalse(UserGPA.objects.exists())
        self.assertFalse(Calculator.objects.exists())
