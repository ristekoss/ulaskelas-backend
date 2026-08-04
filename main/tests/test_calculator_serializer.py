from types import SimpleNamespace
from unittest.mock import patch

from django.test import SimpleTestCase

from main.serializers import CalculatorSerializer


class CalculatorSerializerTest(SimpleTestCase):
    def setUp(self):
        self.calculator = SimpleNamespace(
            id=1,
            user=SimpleNamespace(username="student"),
            course=SimpleNamespace(
                id=2,
                name="Dasar-Dasar Pemrograman",
                sks=4,
                code="CSGE601020",
            ),
            total_score=85,
            total_percentage=100,
        )

    @patch(
        "main.serializers.get_config",
        return_value={"CSGE": "Computer Science - General"},
    )
    def test_includes_course_code_and_description(self, get_config):
        data = CalculatorSerializer(self.calculator).data

        self.assertEqual(data["course_code"], "CSGE601020")
        self.assertEqual(data["course_code_desc"], "Computer Science - General")
        get_config.assert_called_once_with("course_prefixes")

    @patch("main.serializers.get_config", return_value={})
    def test_course_code_description_is_null_for_unknown_prefix(self, _get_config):
        data = CalculatorSerializer(self.calculator).data

        self.assertIsNone(data["course_code_desc"])
