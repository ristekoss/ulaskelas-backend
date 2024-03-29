from django.test import TestCase
from main.models import Course, Curriculum, Tag
# Create your tests here.


class CourseModelTest(TestCase):
    """
    Unit test for model Course.
    """

    def setUp(self):
        self.tag1 = Tag.objects.create(name="Tags 1")
        self.tag2 = Tag.objects.create(name="Tags 2")
        self.curr16 = Curriculum.objects.create(name="2016", year=2016)
        self.curr19 = Curriculum.objects.create(name="2019", year=2019)
        self.course1 = Course.objects.create(
            code="CSCE000001",
            name="Course 1",
            aliasName="C1",
            sks=3,
            description="This is course 1"
        )

    def test_can_add_curriculums(self):
        self.course1.curriculums.add(self.curr16)
        self.course1.curriculums.add(self.curr19)

        self.assertIn(self.curr16, self.course1.curriculums.all())
        self.assertIn(self.curr19, self.course1.curriculums.all())
        self.assertIn(self.course1, self.curr16.course_set.all())
        self.assertIn(self.course1, self.curr19.course_set.all())

    def test_can_add_tags(self):
        self.course1.tags.add(self.tag1)
        self.course1.tags.add(self.tag2)

        self.assertIn(self.tag1, self.course1.tags.all())
        self.assertIn(self.tag2, self.course1.tags.all())
        self.assertIn(self.course1, self.tag1.course_set.all())
        self.assertIn(self.course1, self.tag2.course_set.all())

    def test_can_add_prerequisites(self):
        course2 = Course.objects.create(
            code="CSCE000002",
            name="Course 2",
            aliasName="C2",
            sks=3,
            description="This is course 2"
        )
        course3 = Course.objects.create(
            code="CSCE000003",
            name="Course 3",
            aliasName="C3",
            sks=3,
            description="This is course 3"
        )
        course4 = Course.objects.create(
            code="CSCE000004",
            name="Course 4",
            aliasName="C4",
            sks=3,
            description="This is course 4"
        )
        course3.prerequisites.add(self.course1)
        course3.prerequisites.add(course2)

        # Course 1 and 2 is prequisites of course 3
        self.assertIn(self.course1, course3.prerequisites.all())
        self.assertIn(course2, course3.prerequisites.all())
        # Course 3 is NOT prequisites of course 1 and 2
        self.assertNotIn(course3, self.course1.prerequisites.all())
        self.assertNotIn(course3, course2.prerequisites.all())

        course4.prerequisites.add(course3)
        # Course 3 is prequisites of course 4
        self.assertIn(course3, course4.prerequisites.all())
        self.assertNotIn(course4, course3.prerequisites.all())
        # The previous course 3 prerequisites still exists
        self.assertIn(self.course1, course3.prerequisites.all())
        self.assertIn(course2, course3.prerequisites.all())


class CourseModelCategoryTest(TestCase):
    def setUp(self):
        self.course = Course.objects.create(
            code="CSCE000001",
            name="Course 1",
            aliasName="C1",
            sks=3,
            description="This is course 1"
        )

    def test_can_get_category_without_tag(self):
        self.assertEqual(self.course.get_category(), '')

    def test_can_get_category_with_mandatory_for_FACULTY_tag(self):
        NAME = 'Wajib Fakultas'
        CATEGORY = Tag.Category.FACULTY
        tag = Tag.objects.create(name=NAME, category=CATEGORY)
        self.course.tags.add(tag)

        self.assertEqual(self.course.get_category(), CATEGORY)

    def test_can_get_category_with_mandatory_for_CS_tag(self):
        NAME = 'Wajib Ilmu Komputer'
        CATEGORY = Tag.Category.CS
        tag = Tag.objects.create(name=NAME, category=CATEGORY)
        tag_IS = Tag.objects.create(
            name='Specialization on IS', category=Tag.Category.IS)
        self.course.tags.add(tag)
        self.course.tags.add(tag_IS)
        self.course.tags.add(tag)

        self.assertEqual(self.course.get_category(), CATEGORY)

    def test_can_get_category_with_mandatory_for_IS_tag(self):
        NAME = 'Wajib Sistem Informasi'
        CATEGORY = Tag.Category.IS
        tag = Tag.objects.create(name=NAME, category=CATEGORY)
        tag_CS = Tag.objects.create(
            name='Specialization on CS', category=Tag.Category.CS)
        self.course.tags.add(tag)
        self.course.tags.add(tag_CS)

        self.assertEqual(self.course.get_category(), CATEGORY)

    def test_can_get_category_with_specialization_for_CS_tag(self):
        NAME = 'Kecerdasan Buatan'
        CATEGORY = Tag.Category.CS
        tag = Tag.objects.create(name=NAME, category=CATEGORY)
        self.course.tags.add(tag)

        self.assertEqual(self.course.get_category(), CATEGORY)

    def test_can_get_category_with_specialization_for_IS_tag(self):
        NAME = 'E-Bisnis'
        CATEGORY = Tag.Category.IS
        tag = Tag.objects.create(name=NAME, category=CATEGORY)
        self.course.tags.add(tag)

        self.assertEqual(self.course.get_category(), CATEGORY)
