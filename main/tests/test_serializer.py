from main.serializers import CurriculumSerializer, PrerequisiteSerializer
from django.test import TestCase
from main.models import Course, Curriculum, Tag
# Create your tests here.


class CurriculumSerializerTest(TestCase):
    def test_serialize_curriculum(self):
        curriculum = Curriculum.objects.create(name='2019', year=2019)
        serializer = CurriculumSerializer(curriculum)

        self.assertEqual(serializer.data['name'], curriculum.name)
        self.assertEqual(serializer.data['year'], curriculum.year)


# class TagSerializerTest(TestCase):
#     def test_serialize_tag_with_category(self):
#         tag = Tag.objects.create(
#             name='Wajib Fakultas', category=Tag.Category.FACULTY)
#         serializer = TagSerializer(tag)

#         self.assertEqual(serializer.data['name'], tag.name)
#         self.assertEqual(serializer.data['category'], tag.category)

#     def test_serialize_tag_without_category(self):
#         tag = Tag.objects.create(name='Wajib Fakultas')
#         serializer = TagSerializer(tag)

#         self.assertEqual(serializer.data['name'], tag.name)
#         self.assertEqual(serializer.data['category'], tag.category)


class PrerequisiteSerializerTest(TestCase):
    def setUp(self):
        self.prerequisite = Course.objects.create(
            code="CSCE000001",
            name="Course 1",
            aliasName="C1",
            sks=3,
            description="This is course 1"
        )

    def test_serialize_prerequisite_without_category(self):
        serializer = PrerequisiteSerializer(self.prerequisite)

        self.assertEqual(serializer.data['name'], self.prerequisite.name)
        self.assertEqual(
            serializer.data['category'], self.prerequisite.get_category())

    def test_serialize_prerequisite_with_category(self):
        tag = Tag.objects.create(
            name='Wajib Fakultas', category=Tag.Category.FACULTY)
        self.prerequisite.tags.add(tag)
        serializer = PrerequisiteSerializer(self.prerequisite)

        self.assertEqual(serializer.data['name'], self.prerequisite.name)
        self.assertEqual(
            serializer.data['category'], self.prerequisite.get_category())
