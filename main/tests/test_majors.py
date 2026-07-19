from unittest.mock import patch

from django.contrib.auth.models import User
from main.models import Course
from rest_framework.test import APITestCase


class MajorsEndpointTest(APITestCase):
    def setUp(self):
        self.user = User.objects.create_user(username="test-user")
        self.client.force_authenticate(self.user)

    @patch(
        "main.views_course.get_config",
        return_value={
            "01": {
                "faculty": "Fakultas A",
                "study_program": "Program Z (Program Z English)",
            },
            "02": {
                "faculty": "Fakultas A",
                "study_program": "Program Z (Program Z English)",
            },
            "03": {
                "faculty": "Fakultas B",
                "study_program": "Program A",
            },
        },
    )
    def test_returns_unique_sorted_local_faculty_program_names(self, _get_config):
        response = self.client.get("/api/majors")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response.data,
            {
                "data": {
                    "majors": ["Fakultas A - Program Z", "Fakultas B - Program A"]
                },
                "error": None,
            },
        )

    @patch(
        "main.views_course.get_config",
        side_effect=lambda key: {
            "kd_org": {
                "01": {
                    "faculty": "Fakultas A",
                    "study_program": "Program Z (Program Z English)",
                }
            },
            "study_program": {"Program Z (Program Z English)": "PZ"},
            "course_prefixes": {},
        }[key],
    )
    def test_courses_can_be_filtered_by_selected_major(self, _get_config):
        Course.objects.create(
            code="PZ000001", curriculum="2024", name="Program Z Course", sks=3, term=1
        )
        Course.objects.create(
            code="PA000001", curriculum="2024", name="Program A Course", sks=3, term=1
        )

        response = self.client.get(
            "/api/courses/?major=Program%20Z&show_all=true"
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            [course["code"] for course in response.data["data"]["courses"]],
            ["PZ000001"],
        )

    @patch(
        "main.views_course.get_config",
        return_value={
            "01": {
                "faculty": "Fakultas A",
                "study_program": "Program Z",
            },
            "course_prefixes": {},
        },
    )
    def test_unmapped_major_returns_bad_request(self, _get_config):
        response = self.client.get("/api/courses/?major=Program%20Z&show_all=true")

        self.assertEqual(response.status_code, 400)
        self.assertEqual(
            response.data["error"], "Major not found or has no course mapping."
        )
