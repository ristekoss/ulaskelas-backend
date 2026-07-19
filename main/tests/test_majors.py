from unittest.mock import patch

from django.contrib.auth.models import User
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
