from io import StringIO
from unittest.mock import MagicMock, call, patch

from django.contrib.auth.models import User
from django.core.management import call_command, CommandError
from django.test import TestCase
from playwright.sync_api import TimeoutError as PlaywrightTimeoutError

from main.integrations.slcm_irs import (
    IRSParseError,
    import_courses,
    parse_latest_history,
    resolve_courses,
)
from main.management.commands.import_slcm_irs import Command, IRS_TABLE_MARKER
from main.models import (
    Calculator,
    Course,
    CourseSemester,
    Profile,
    UserCumulativeGPA,
    UserGPA,
)


class SLCMIRSParserTest(TestCase):
    def test_parser_selects_latest_period_and_deduplicates_codes(self):
        history = parse_latest_history(
            [
                {
                    "headers": [
                        "Periode Akademik",
                        "Kode MK",
                        "Nama Mata Kuliah",
                        "SKS",
                    ],
                    "rows": [
                        [
                            "2024/2025 Ganjil",
                            "OLD600001",
                            "Old Course",
                            "3",
                        ],
                        [
                            "2024/2025 Genap",
                            " csge 601020 ",
                            "Dasar Pemrograman",
                            "4 SKS",
                        ],
                        [
                            "2024/2025 Genap",
                            "CSGE601020",
                            "Dasar Pemrograman",
                            "4",
                        ],
                        [
                            "2024/2025 Genap",
                            "UIGE600001",
                            "MPKT",
                            "5",
                        ],
                    ],
                }
            ]
        )

        self.assertEqual(history["period"], "2024/2025 Genap")
        self.assertEqual(
            history["courses"],
            [
                {
                    "code": "CSGE601020",
                    "name": "Dasar Pemrograman",
                    "credits": 4,
                },
                {"code": "UIGE600001", "name": "MPKT", "credits": 5},
            ],
        )

    def test_parser_selects_latest_non_empty_separate_period_table(self):
        history = parse_latest_history(
            [
                {
                    "headers": ["Course Code", "Course Name", "Credits"],
                    "period_label": "2023/2024 Genap",
                    "rows": [["OLD000001", "Old", "2"]],
                },
                {
                    "headers": ["Kode", "Mata Kuliah", "Jumlah SKS"],
                    "period_label": "2024/2025 Ganjil",
                    "rows": [
                        ["NEW000001", "New A", "3"],
                        ["NEW000002", "New B", "2"],
                    ],
                },
            ]
        )

        self.assertEqual(history["period"], "2024/2025 Ganjil")
        self.assertEqual(
            [course["code"] for course in history["courses"]],
            ["NEW000001", "NEW000002"],
        )

    def test_parser_selects_latest_slcm_separator_period(self):
        history = parse_latest_history(
            [
                {
                    "headers": [
                        "No.",
                        "Kode MK",
                        "Kurikulum",
                        "Nama MK",
                        "Kelas",
                        "SKS",
                    ],
                    "row_periods": [
                        "Tahun Ajaran 2024/2025 Term 2",
                        "Tahun Ajaran 2025/2026 Term 1",
                        "Tahun Ajaran 2025/2026 Term 2",
                    ],
                    "rows": [
                        ["1.", "OLD600001", "2024", "Old", "A", "3"],
                        ["2.", "MID600001", "2024", "Middle", "A", "3"],
                        ["3.", "NEW600001", "2024", "Newest", "A", "4"],
                    ],
                }
            ]
        )

        self.assertEqual(history["period"], "Tahun Ajaran 2025/2026 Term 2")
        self.assertEqual(
            history["courses"],
            [{"code": "NEW600001", "name": "Newest", "credits": 4}],
        )

    def test_parser_skips_newer_empty_period(self):
        history = parse_latest_history(
            [
                {
                    "headers": ["Kode MK", "Nama Mata Kuliah", "SKS"],
                    "period_label": "2025/2026 Ganjil",
                    "rows": [
                        ["", "Summary row", ""],
                        ["", "Another summary row", ""],
                        ["", "Total", "5"],
                    ],
                },
                {
                    "headers": ["Kode", "Mata Kuliah", "Jumlah SKS"],
                    "period_label": "2024/2025 Genap",
                    "rows": [["VALID0001", "Valid Course", "3"]],
                },
            ]
        )

        self.assertEqual(
            history,
            {
                "period": "2024/2025 Genap",
                "courses": [
                    {"code": "VALID0001", "name": "Valid Course", "credits": 3}
                ],
            },
        )

    def test_parser_orders_short_term_after_even_term(self):
        history = parse_latest_history(
            [
                {
                    "headers": [
                        "Term",
                        "Course Code",
                        "Course Name",
                        "Credits",
                    ],
                    "rows": [
                        ["2024/2025 Genap", "EVEN00001", "Even", "3"],
                        ["2024/2025 Pendek", "SHORT0001", "Short", "2"],
                    ],
                }
            ]
        )

        self.assertEqual(history["period"], "2024/2025 Pendek")
        self.assertEqual(
            history["courses"],
            [{"code": "SHORT0001", "name": "Short", "credits": 2}],
        )

    def test_parser_treats_unlabelled_course_table_as_active_slcm_period(self):
        history = parse_latest_history(
            [
                {
                    "headers": [
                        "No.",
                        "Kode MK",
                        "Nama MK",
                        "SKS",
                        "Jenis Kelas",
                        "Tanggal Pengisian",
                        "Penyelenggara",
                    ],
                    "row_periods": [""],
                    "rows": [
                        [
                            "1",
                            "VALID0001",
                            "Valid Course",
                            "3",
                            "Reguler",
                            "-",
                            "Fakultas A",
                        ]
                    ],
                }
            ]
        )

        self.assertEqual(history["period"], "Periode Aktif SLCM")
        self.assertEqual(
            history["courses"],
            [{"code": "VALID0001", "name": "Valid Course", "credits": 3}],
        )

    def test_parser_rejects_unorderable_period(self):
        with self.assertRaisesMessage(IRSParseError, "could not be ordered"):
            parse_latest_history(
                [
                    {
                        "headers": ["Kode", "Mata Kuliah", "SKS"],
                        "period_label": "Periode terbaru",
                        "rows": [["VALID0001", "Valid Course", "3"]],
                    }
                ]
            )

    def test_parser_supports_compact_numeric_period(self):
        history = parse_latest_history(
            [
                {
                    "headers": ["Periode", "Kode", "Mata Kuliah", "SKS"],
                    "rows": [
                        ["2024-1", "ODD000001", "Odd", "3"],
                        ["2024-2", "EVEN00001", "Even", "3"],
                    ],
                }
            ]
        )

        self.assertEqual(
            history,
            {
                "period": "2024-2",
                "courses": [
                    {"code": "EVEN00001", "name": "Even", "credits": 3}
                ],
            },
        )

    def test_parser_rejects_unrecognized_page(self):
        with self.assertRaises(IRSParseError):
            parse_latest_history(
                [{"headers": ["Tanggal", "Keterangan"], "rows": [["1", "Test"]]}]
            )

    def test_parser_deduplicates_courses_across_same_period_tables(self):
        history = parse_latest_history(
            [
                {
                    "headers": ["Kode", "Mata Kuliah", "SKS"],
                    "period_label": "2024/2025 Genap",
                    "rows": [["VALID0001", "Valid Course", "3"]],
                },
                {
                    "headers": ["Kode", "Mata Kuliah", "SKS"],
                    "period_label": "2024/2025 Genap",
                    "rows": [["VALID0001", "Valid Course", "3"]],
                },
            ]
        )

        self.assertEqual(
            history["courses"],
            [{"code": "VALID0001", "name": "Valid Course", "credits": 3}],
        )


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
        "main.integrations.slcm_irs.add_semester_gpa",
        side_effect=RuntimeError("forced failure"),
    )
    def test_import_rolls_back_all_changes(self, _add_semester_gpa):
        with self.assertRaises(RuntimeError):
            import_courses(self.profile, "1", [self.course])

        self.assertFalse(UserCumulativeGPA.objects.exists())
        self.assertFalse(UserGPA.objects.exists())
        self.assertFalse(Calculator.objects.exists())
        self.assertFalse(CourseSemester.objects.exists())

    def test_import_rejects_empty_course_list_without_creating_semester(self):
        with self.assertRaisesMessage(ValueError, "At least one resolved course"):
            import_courses(self.profile, "1", [])

        self.assertFalse(UserCumulativeGPA.objects.exists())
        self.assertFalse(UserGPA.objects.exists())

    @patch(
        "main.management.commands.import_slcm_irs.Command._scrape",
        return_value={
            "period": "2024/2025 Genap",
            "courses": [
                {
                    "code": "CSGE601020",
                    "name": "Dasar Pemrograman",
                    "credits": 4,
                }
            ],
        },
    )
    def test_management_command_dry_run_does_not_write(self, _scrape):
        stdout = StringIO()

        call_command(
            "import_slcm_irs",
            username=self.profile.username,
            semester="1",
            irs_url="https://slcm.ui.ac.id/student/irs",
            dry_run=True,
            stdout=stdout,
        )

        self.assertIn("Dry run", stdout.getvalue())
        self.assertIn("2024/2025 Genap", stdout.getvalue())
        self.assertFalse(UserCumulativeGPA.objects.exists())
        self.assertFalse(UserGPA.objects.exists())
        self.assertFalse(Calculator.objects.exists())


class SLCMIRSBrowserFlowTest(TestCase):
    @patch(
        "main.management.commands.import_slcm_irs.parse_latest_history",
        return_value={"period": "2024/2025 Genap", "courses": []},
    )
    @patch(
        "main.management.commands.import_slcm_irs.collect_page_tables",
        return_value=[{"headers": [], "rows": []}],
    )
    @patch("playwright.sync_api.sync_playwright")
    @patch("builtins.input", side_effect=AssertionError("input must not be called"))
    def test_scrape_waits_for_login_and_reads_irs_automatically(
        self,
        _input,
        sync_playwright,
        _collect_page_tables,
        _parse_latest_history,
    ):
        playwright = sync_playwright.return_value.__enter__.return_value
        browser = playwright.chromium.launch.return_value
        context = browser.new_context.return_value
        page = context.new_page.return_value
        frame = MagicMock()
        page.frames = [frame]
        irs_url = "https://slcm.ui.ac.id/student/irs"

        result = Command()._scrape(irs_url, 12)

        self.assertEqual(result["period"], "2024/2025 Genap")
        self.assertEqual(
            page.goto.call_args_list,
            [call(irs_url, wait_until="domcontentloaded")],
        )
        page.wait_for_function.assert_called_once_with(
            IRS_TABLE_MARKER, timeout=12000
        )
        context.close.assert_called_once()
        browser.close.assert_called_once()

    @patch("playwright.sync_api.sync_playwright")
    def test_scrape_reports_login_timeout(self, sync_playwright):
        playwright = sync_playwright.return_value.__enter__.return_value
        page = (
            playwright.chromium.launch.return_value
            .new_context.return_value
            .new_page.return_value
        )
        page.wait_for_function.side_effect = PlaywrightTimeoutError("timeout")

        with self.assertRaisesMessage(CommandError, "Timed out waiting"):
            Command()._scrape(
                "https://slcm.ui.ac.id/student/irs",
                1,
            )

    def test_rejects_invalid_irs_url(self):
        with self.assertRaisesMessage(CommandError, "valid HTTP(S) URL"):
            Command()._validate_irs_url("not-a-url")
