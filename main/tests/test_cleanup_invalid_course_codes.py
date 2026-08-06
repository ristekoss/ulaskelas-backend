from io import StringIO

from django.contrib.auth.models import User
from django.core.management import call_command
from django.test import TestCase

from main.models import (
    Calculator,
    Course,
    Profile,
    StudyProgram,
    StudyProgramCourse,
)


class CleanupInvalidCourseCodesTest(TestCase):
    def setUp(self):
        auth_user = User.objects.create_user(username="test-user")
        self.profile = Profile.objects.create(
            user=auth_user,
            username="test-user",
            name="Test User",
            npm="2200000000",
            faculty="Fakultas A",
            study_program="Program A",
            educational_program="S1 Reguler",
            role="student",
            org_code="01",
        )
        self.program = StudyProgram.objects.create(
            org_code="01",
            faculty="Fakultas A",
            study_program="Program A",
            educational_program="S1 Reguler",
        )

    def create_course(self, code, name):
        return Course.objects.create(
            code=code,
            curriculum="2024",
            name=name,
            sks=3,
            term=1,
        )

    def create_mapping(self, course):
        return StudyProgramCourse.objects.create(
            study_program=self.program,
            course=course,
            program_term=1,
        )

    def test_dry_run_does_not_modify_invalid_courses(self):
        course = self.create_course("None", "Polluted Course")
        mapping = self.create_mapping(course)
        stdout = StringIO()

        call_command("cleanup_invalid_course_codes", stdout=stdout)

        self.assertTrue(Course.objects.filter(pk=course.pk).exists())
        mapping.refresh_from_db()
        self.assertTrue(mapping.is_active)
        self.assertIn("DRY RUN: 1 candidate(s)", stdout.getvalue())

    def test_apply_deletes_unreferenced_invalid_course(self):
        course = self.create_course("N/A", "Unreferenced Course")
        self.create_mapping(course)

        call_command("cleanup_invalid_course_codes", "--apply", stdout=StringIO())

        self.assertFalse(Course.objects.filter(pk=course.pk).exists())

    def test_apply_retains_referenced_course_and_deactivates_mapping(self):
        course = self.create_course("null", "Referenced Course")
        mapping = self.create_mapping(course)
        calculator = Calculator.objects.create(user=self.profile, course=course)

        call_command("cleanup_invalid_course_codes", "--apply", stdout=StringIO())

        self.assertTrue(Course.objects.filter(pk=course.pk).exists())
        self.assertTrue(Calculator.objects.filter(pk=calculator.pk).exists())
        mapping.refresh_from_db()
        self.assertFalse(mapping.is_active)

    def test_apply_does_not_touch_valid_course(self):
        course = self.create_course("CSGE601012", "Valid Course")
        mapping = self.create_mapping(course)

        call_command("cleanup_invalid_course_codes", "--apply", stdout=StringIO())

        self.assertTrue(Course.objects.filter(pk=course.pk).exists())
        mapping.refresh_from_db()
        self.assertTrue(mapping.is_active)
