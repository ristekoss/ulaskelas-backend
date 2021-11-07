from rest_framework import serializers

from .models import Course, Review, ReviewLike, Tag


# class CurriculumSerializer(serializers.ModelSerializer):
#     class Meta:
#         model = Curriculum
#         fields = ['name', 'year']


class TagSerializer(serializers.ModelSerializer):
    class Meta:
        model = Tag
        fields = ['tag_name']


# class PrerequisiteSerializer(serializers.ModelSerializer):
#     category = serializers.CharField(source='get_category', read_only=True)

#     class Meta:
#         model = Course
#         fields = ['name', 'category']


class CourseSerializer(serializers.ModelSerializer):
    # prerequisites = PrerequisiteSerializer(read_only=True, many=True)
    # curriculums = CurriculumSerializer(read_only=True, many=True)
    tags = TagSerializer(read_only=True, many=True)
    review_count = serializers.IntegerField()

    class Meta:
        model = Course
        fields = ('code', 'curriculum', 'name', 'description', 'sks', 'term', 'prerequisites', 'review_count', 'tags')

class ReviewSerializer(serializers.ModelSerializer):
    likes_by = serializers.SerializerMethodField('get_likes')
    author = serializers.SerializerMethodField('get_author')
    course_code = serializers.SerializerMethodField('get_course_code')

    class Meta:
        model = Review
        fields = ('author','course_code','created_at','updated_at','academic_year',
        'semester','content','hate_speech_status','sentimen','is_anonym', 'likes_by')

    def get_author(self, obj):
        return obj.user.username

    def get_course_code(self, obj):
        return obj.course.code
    
    def get_likes(self, obj):
        try:
            review_likes = self.context['review_likes'].filter(review=obj)
        except:
            review_likes = []
        likes = []
        for like in review_likes:
            likes.append(like.user.username)
        return likes