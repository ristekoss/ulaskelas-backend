from rest_framework import serializers

from .models import Course, Curriculum, Tag


class CourseSerializer(serializers.ModelSerializer):
    class Meta:
        model = Course
        fields = "__all__"


class CurriculumSerializer(serializers.ModelSerializer):
    class Meta:
        model = Curriculum
        fields = ['name', 'year']


class TagSerializer(serializers.ModelSerializer):
    class Meta:
        model = Tag
        fields = ['name', 'category']


class PrerequisiteSerializer(serializers.ModelSerializer):
    category = serializers.CharField(source='get_category', read_only=True)

    class Meta:
        model = Course
        fields = ['name', 'category']
