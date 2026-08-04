from django.contrib.auth.models import User
from django.utils import timezone
from rest_framework.test import APITestCase

from main.models import (
    Course,
    CourseSemester,
    Profile,
    StudyProgram,
    StudyProgramCourse,
    UserGPA,
)


class CrossFacultyGPATest(APITestCase):
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

    def create_catalog(self):
        program = StudyProgram.objects.create(
            org_code="01",
            faculty="Fakultas A",
            study_program="Program A",
            educational_program="S1 Reguler",
            last_synced_at=timezone.now(),
        )
        course = Course.objects.create(
            code="AA000001",
            curriculum="2024",
            name="Non Fasilkom Course",
            sks=3,
            term=8,
        )
        StudyProgramCourse.objects.create(
            study_program=program,
            course=course,
            program_term=1,
        )
        return course

    def test_get_catalog_uses_profile_org_code_and_program_term(self):
        course = self.create_catalog()

        response = self.client.get("/api/calculator-gpa")

        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.data["data"]["course_catalog_available"])
        self.assertEqual(
            response.data["data"]["courses"][1],
            [{"id": course.id, "name": "Non Fasilkom Course"}],
        )

    def test_auto_fill_uses_program_mapping(self):
        course = self.create_catalog()

        response = self.client.post(
            "/api/calculator-gpa?is_auto_fill=true",
            {"given_semesters": ["1"]},
            format="json",
        )

        self.assertEqual(response.status_code, 201)
        semester = UserGPA.objects.get(given_semester="1")
        self.assertTrue(
            CourseSemester.objects.filter(semester=semester, course=course).exists()
        )

    def test_auto_fill_rejects_unsynchronized_program_without_partial_semester(self):
        response = self.client.post(
            "/api/calculator-gpa?is_auto_fill=true",
            {"given_semesters": ["1"]},
            format="json",
        )

        self.assertEqual(response.status_code, 409)
        self.assertEqual(
            response.data["error"]["code"], "COURSE_CATALOG_UNAVAILABLE"
        )
        self.assertFalse(UserGPA.objects.exists())

    def test_false_auto_fill_does_not_add_courses(self):
        self.create_catalog()

        response = self.client.post(
            "/api/calculator-gpa?is_auto_fill=false",
            {"given_semesters": ["1"]},
            format="json",
        )

        self.assertEqual(response.status_code, 201)
        self.assertFalse(CourseSemester.objects.exists())
