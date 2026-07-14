from django.test import TestCase
from django.contrib.auth.models import User
from rest_framework.test import APIRequestFactory

from main.models import (
    Calculator,
    Course,
    CourseSemester,
    Profile,
    ScoreComponent,
    ScoreSubcomponent,
    UserCumulativeGPA,
    UserGPA,
)
from main.utils import get_calculator_progress, get_calculator_status
from main.views_gpa_calculator import calculator_status


class GradeStatusTest(TestCase):
    def setUp(self):
        self.auth_user = User.objects.create_user(
            username="test-user", password="password"
        )
        self.profile = Profile.objects.create(
            user=self.auth_user,
            username="test-user",
            name="Test User",
            npm="2200000000",
            faculty="Fasilkom",
            study_program="Ilmu Komputer",
            educational_program="S1",
            role="student",
            org_code="TEST",
        )
        self.course = Course.objects.create(
            code="CS000001",
            curriculum="2024",
            name="Test Course",
            sks=3,
            term=1,
        )
        cumulative_gpa = UserCumulativeGPA.objects.create(user=self.profile)
        self.semester = UserGPA.objects.create(
            userCumulativeGPA=cumulative_gpa,
            given_semester="Semester 1",
        )

    def create_calculator(self, total_percentage):
        calculator = Calculator.objects.create(
            user=self.profile,
            course=self.course,
            total_percentage=total_percentage,
        )
        CourseSemester.objects.create(
            semester=self.semester,
            course=self.course,
            calculator=calculator,
        )
        return calculator

    def test_weight_incomplete_has_priority(self):
        calculator = self.create_calculator(75)
        component = ScoreComponent.objects.create(
            calculator=calculator,
            name="Quiz",
            weight=75,
            score=80,
        )
        ScoreSubcomponent.objects.create(
            score_component=component,
            subcomponent_number=1,
            subcomponent_score=None,
        )

        self.assertEqual(
            get_calculator_status(calculator),
            {"code": "WEIGHT_INCOMPLETE", "label": "Bobot belum terisi"},
        )

    def test_missing_subcomponent_score_is_incomplete(self):
        calculator = self.create_calculator(100)
        component = ScoreComponent.objects.create(
            calculator=calculator,
            name="Quiz",
            weight=100,
            score=40,
        )
        ScoreSubcomponent.objects.create(
            score_component=component,
            subcomponent_number=1,
            subcomponent_score=None,
        )

        self.assertEqual(
            get_calculator_status(calculator),
            {"code": "SCORE_INCOMPLETE", "label": "Nilai ada yang belum terisi"},
        )

    def test_fully_scored_calculator_is_complete(self):
        calculator = self.create_calculator(100)
        component = ScoreComponent.objects.create(
            calculator=calculator,
            name="Quiz",
            weight=100,
            score=0,
        )
        ScoreSubcomponent.objects.create(
            score_component=component,
            subcomponent_number=1,
            subcomponent_score=0,
        )

        self.assertEqual(
            get_calculator_status(calculator),
            {"code": "COMPLETE", "label": "Nilai lengkap"},
        )

    def test_progress_counts_subcomponents_and_zero_as_filled(self):
        calculator = self.create_calculator(60)
        component = ScoreComponent.objects.create(
            calculator=calculator,
            name="Quiz",
            weight=60,
            score=40,
        )
        for number, score in enumerate([0, 70, None, None, 80], start=1):
            ScoreSubcomponent.objects.create(
                score_component=component,
                subcomponent_number=number,
                subcomponent_score=score,
            )

        self.assertEqual(
            get_calculator_progress(calculator),
            {
                "weight_progress": {"filled": 60, "total": 100, "percentage": 60},
                "score_progress": {"filled": 3, "total": 5, "percentage": 60},
            },
        )

    def test_calculator_status_uses_highest_numeric_semester(self):
        higher_semester = UserGPA.objects.create(
            userCumulativeGPA=self.semester.userCumulativeGPA,
            given_semester="10",
        )
        higher_course = Course.objects.create(
            code="CS000002",
            curriculum="2024",
            name="Higher Semester Course",
            sks=3,
            term=10,
        )
        calculator = Calculator.objects.create(
            user=self.profile,
            course=higher_course,
            total_percentage=100,
        )
        CourseSemester.objects.create(
            semester=higher_semester,
            course=higher_course,
            calculator=calculator,
        )

        request = APIRequestFactory().get("/calculator-status")
        request.user = self.auth_user
        result = calculator_status(request)

        self.assertEqual(result.data["semester"], "10")
        self.assertEqual(
            result.data["courses"][0]["course_name"], "Higher Semester Course"
        )
