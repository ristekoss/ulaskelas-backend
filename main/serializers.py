from rest_framework import serializers

# from .models import Course, Curriculum, Tag
from .models import Profile, Review


# class CurriculumSerializer(serializers.ModelSerializer):
#     class Meta:
#         model = Curriculum
#         fields = ['name', 'year']


# class TagSerializer(serializers.ModelSerializer):
#     class Meta:
#         model = Tag
#         fields = ['name', 'category']


# class PrerequisiteSerializer(serializers.ModelSerializer):
#     category = serializers.CharField(source='get_category', read_only=True)

#     class Meta:
#         model = Course
#         fields = ['name', 'category']


# class CourseSerializer(serializers.ModelSerializer):
#     prerequisites = PrerequisiteSerializer(read_only=True, many=True)
#     curriculums = CurriculumSerializer(read_only=True, many=True)
#     tags = TagSerializer(read_only=True, many=True)

#     class Meta:
#         model = Course
#         fields = "__all__"

class ReviewSerializer(serializers.ModelSerializer):
    class Meta:
        model = Review
        fields = "__all__"