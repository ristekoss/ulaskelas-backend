from unittest.mock import patch

from django.test import TestCase

from courseUpdater.courseApi import CourseSyncError, _apply_courses_payload
from main.models import Course, StudyProgram, StudyProgramCourse


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
