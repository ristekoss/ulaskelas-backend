from unittest.mock import patch

from django.contrib.auth.models import User
from main.models import Course, StudyProgram, StudyProgramCourse
from rest_framework.test import APITestCase


PROGRAM_CONFIG = {
    "01": {
        "faculty": "Fakultas A (Faculty A)",
        "study_program": "Program Z (Program Z English)",
        "educational_program": "S1 Reguler (Undergraduate Program)",
    },
    "02": {
        "faculty": "Fakultas B",
        "study_program": "Program A",
        "educational_program": "D3 (Diploma III)",
    },
    "03": {
        "faculty": "Fakultas B",
        "study_program": "Program Pascasarjana",
        "educational_program": "S2 (Graduate Program)",
    },
}


class MajorsEndpointTest(APITestCase):
    def setUp(self):
        self.user = User.objects.create_user(username="test-user")
        self.client.force_authenticate(self.user)

    @patch("main.views_course.get_config", return_value=PROGRAM_CONFIG)
    def test_returns_supported_program_objects_and_availability(self, _get_config):
        program = StudyProgram.objects.create(
            org_code="01",
            faculty="Fakultas A",
            study_program="Program Z",
            educational_program="S1 Reguler",
        )
        course = Course.objects.create(
            code="PZ000001",
            curriculum="2024",
            name="Program Z Course",
            sks=3,
            term=1,
        )
        StudyProgramCourse.objects.create(
            study_program=program,
            course=course,
            program_term=1,
        )

        response = self.client.get("/api/majors")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response.data["data"]["faculties"],
            [
                {"id": "Fakultas A", "name": "Fakultas A"},
                {"id": "Fakultas B", "name": "Fakultas B"},
            ],
        )
        self.assertEqual(
            response.data["data"]["majors"],
            [
                {
                    "id": "01",
                    "org_code": "01",
                    "faculty": "Fakultas A",
                    "study_program": "Program Z",
                    "educational_program": "S1 Reguler",
                    "display_name": "Fakultas A - Program Z - S1 Reguler",
                    "available": True,
                },
                {
                    "id": "02",
                    "org_code": "02",
                    "faculty": "Fakultas B",
                    "study_program": "Program A",
                    "educational_program": "D3",
                    "display_name": "Fakultas B - Program A - D3",
                    "available": False,
                },
            ],
        )

    @patch("main.views_course.get_config", return_value=PROGRAM_CONFIG)
    def test_versioned_and_unversioned_majors_have_the_same_contract(self, _get_config):
        unversioned = self.client.get("/api/majors")
        versioned = self.client.get("/api/v1/majors")

        self.assertEqual(unversioned.status_code, 200)
        self.assertEqual(versioned.status_code, 200)
        self.assertEqual(versioned.data, unversioned.data)

    @patch("main.views_course.get_config", return_value=PROGRAM_CONFIG)
    def test_courses_can_filter_by_full_faculty_name_and_legacy_id(self, _get_config):
        programs = [
            StudyProgram.objects.create(
                org_code="01",
                faculty="Fakultas A",
                study_program="Program Z",
                educational_program="S1 Reguler",
            ),
            StudyProgram.objects.create(
                org_code="02",
                faculty="Fakultas B",
                study_program="Program A",
                educational_program="D3",
            ),
        ]
        courses = [
            Course.objects.create(
                code="PZ000001", curriculum="2024", name="Course A", sks=3, term=1
            ),
            Course.objects.create(
                code="PA000001", curriculum="2024", name="Course B", sks=3, term=1
            ),
        ]
        for program, course in zip(programs, courses):
            StudyProgramCourse.objects.create(
                study_program=program, course=course, program_term=1
            )

        by_name = self.client.get(
            "/api/courses/?show_all=true&faculty=fAkUlTaS%20a"
        )
        by_legacy_id = self.client.get(
            "/api/courses/?show_all=true&faculty=02"
        )
        multiple = self.client.get(
            "/api/courses/?show_all=true&faculty=Fakultas%20A,Fakultas%20B"
        )

        self.assertEqual(
            [course["code"] for course in by_name.data["data"]["courses"]],
            ["PZ000001"],
        )
        self.assertEqual(
            [course["code"] for course in by_legacy_id.data["data"]["courses"]],
            ["PA000001"],
        )
        self.assertEqual(
            {course["code"] for course in multiple.data["data"]["courses"]},
            {"PZ000001", "PA000001"},
        )

    @patch("main.views_course.get_config", return_value=PROGRAM_CONFIG)
    def test_unknown_faculty_filter_returns_no_courses(self, _get_config):
        response = self.client.get(
            "/api/courses/?show_all=true&faculty=Unknown%20Faculty"
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["data"]["courses"], [])

    @patch("main.views_course.get_config", return_value=PROGRAM_CONFIG)
    def test_courses_filter_uses_org_code_and_program_metadata(self, _get_config):
        program = StudyProgram.objects.create(
            org_code="01",
            faculty="Fakultas A",
            study_program="Program Z",
            educational_program="S1 Reguler",
        )
        matching = Course.objects.create(
            code="PZ000001", curriculum="2024", name="Program Z Course", sks=3, term=8
        )
        other = Course.objects.create(
            code="PA000001", curriculum="2024", name="Program A Course", sks=3, term=1
        )
        StudyProgramCourse.objects.create(
            study_program=program,
            course=matching,
            program_term=2,
            course_type=StudyProgramCourse.CourseType.MANDATORY,
            category=StudyProgramCourse.Category.INTERNAL,
        )
        StudyProgramCourse.objects.create(
            study_program=program,
            course=other,
            program_term=1,
            course_type=StudyProgramCourse.CourseType.ELECTIVE,
            category=StudyProgramCourse.Category.SHARED,
        )

        response = self.client.get(
            "/api/courses/?major=01&term=2&course_type=MANDATORY"
            "&category=INTERNAL&show_all=true"
        )

        self.assertEqual(response.status_code, 200)
        courses = response.data["data"]["courses"]
        self.assertEqual([course["code"] for course in courses], ["PZ000001"])
        self.assertEqual(courses[0]["program_term"], 2)
        self.assertEqual(courses[0]["course_type"], "MANDATORY")
        self.assertEqual(courses[0]["category"], "INTERNAL")
        self.assertEqual(
            courses[0]["faculties"], [{"id": "01", "name": "Fakultas A"}]
        )

        multiple = self.client.get(
            "/api/courses/?major=01&category=INTERNAL,SHARED&show_all=true"
        )
        self.assertEqual(
            {course["category"] for course in multiple.data["data"]["courses"]},
            {"INTERNAL", "SHARED"},
        )

        invalid = self.client.get(
            "/api/courses/?major=01&category=INVALID&show_all=true"
        )
        self.assertEqual(invalid.data["data"]["courses"], [])

    @patch("main.views_course.get_config", return_value=PROGRAM_CONFIG)
    def test_cross_program_category_filter_uses_active_mappings(self, _get_config):
        program = StudyProgram.objects.create(
            org_code="01",
            faculty="Fakultas A",
            study_program="Program Z",
            educational_program="S1 Reguler",
        )
        course = Course.objects.create(
            code="SHARED01", curriculum="2024", name="Shared", sks=3, term=1
        )
        StudyProgramCourse.objects.create(
            study_program=program,
            course=course,
            program_term=1,
            category=StudyProgramCourse.Category.SHARED,
        )

        response = self.client.get(
            "/api/courses/?show_all=true&category=SHARED"
        )

        self.assertEqual(
            [item["code"] for item in response.data["data"]["courses"]],
            ["SHARED01"],
        )
        self.assertEqual(response.data["data"]["courses"][0]["category"], "UNKNOWN")

    @patch("main.views_course.get_config", return_value=PROGRAM_CONFIG)
    def test_unknown_or_unsupported_major_returns_bad_request(self, _get_config):
        response = self.client.get("/api/courses/?major=03&show_all=true")

        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.data["error"]["code"], "MAJOR_NOT_SUPPORTED")

    @patch("main.views_course.get_config", return_value=PROGRAM_CONFIG)
    def test_show_all_excludes_courses_without_active_programs(self, _get_config):
        program = StudyProgram.objects.create(
            org_code="01",
            faculty="Fakultas A",
            study_program="Program Z",
            educational_program="S1 Reguler",
        )
        active_course = Course.objects.create(
            code="ACTIVE01", curriculum="2024", name="Active", sks=3, term=1
        )
        inactive_course = Course.objects.create(
            code="INACT001", curriculum="2024", name="Inactive", sks=3, term=1
        )
        StudyProgramCourse.objects.create(
            study_program=program,
            course=active_course,
            program_term=1,
        )
        StudyProgramCourse.objects.create(
            study_program=program,
            course=inactive_course,
            program_term=1,
            is_active=False,
        )

        response = self.client.get("/api/courses/?show_all=true")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            [course["code"] for course in response.data["data"]["courses"]],
            ["ACTIVE01"],
        )

    def test_course_detail_returns_unique_faculties_from_active_programs(self):
        course = Course.objects.create(
            code="UI000001",
            curriculum="2024",
            name="Cross-faculty Course",
            sks=3,
            term=1,
        )
        programs = [
            StudyProgram.objects.create(
                org_code="01.00.12.01",
                faculty="ILMU KOMPUTER",
                study_program="Ilmu Komputer",
                educational_program="S1 Reguler",
            ),
            StudyProgram.objects.create(
                org_code="06.00.12.01",
                faculty="ILMU KOMPUTER",
                study_program="Sistem Informasi",
                educational_program="S1 Reguler",
            ),
            StudyProgram.objects.create(
                org_code="01.00.13.01",
                faculty="ILMU KEPERAWATAN",
                study_program="Ilmu Keperawatan",
                educational_program="S1 Reguler",
            ),
        ]
        for program in programs:
            StudyProgramCourse.objects.create(
                study_program=program,
                course=course,
                program_term=1,
            )

        inactive_program = StudyProgram.objects.create(
            org_code="01.00.10.01",
            faculty="KESEHATAN MASYARAKAT",
            study_program="Kesehatan Masyarakat",
            educational_program="S1 Reguler",
        )
        StudyProgramCourse.objects.create(
            study_program=inactive_program,
            course=course,
            program_term=1,
            is_active=False,
        )

        response = self.client.get("/api/courses/{}/".format(course.id))

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response.data["data"]["course"]["faculties"],
            [
                {"id": "13", "name": "ILMU KEPERAWATAN"},
                {"id": "12", "name": "ILMU KOMPUTER"},
            ],
        )
