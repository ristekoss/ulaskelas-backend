from live_config.views import get_config
from main.utils import get_profile_term
from rest_framework import serializers

from .models import Course, Profile, Review, Tag, Bookmark

# class CurriculumSerializer(serializers.ModelSerializer):
#     class Meta:
#         model = Curriculum
#         fields = ['name', 'year']


# class TagSerializer(serializers.ModelSerializer):
#     class Meta:
#         model = Tag
#         fields = ['tag_name']


# class PrerequisiteSerializer(serializers.ModelSerializer):
#     category = serializers.CharField(source='get_category', read_only=True)

#     class Meta:
#         model = Course
#         fields = ['name', 'category']


class CourseSerializer(serializers.ModelSerializer):
    # prerequisites = PrerequisiteSerializer(read_only=True, many=True)
    # curriculums = CurriculumSerializer(read_only=True, many=True)
    review_count = serializers.SerializerMethodField('get_review_count')
    code_desc = serializers.SerializerMethodField('get_code_desc')
    tags = serializers.SerializerMethodField('get_top_tags')
    
    def get_code_desc(self, obj):
        course_prefixes = get_config('course_prefixes')
        code = obj.code[:4]
        if code in course_prefixes:
            return course_prefixes[code]
        return None

    def get_review_count(self, obj):
        return obj.reviews.count()
    
    def get_top_tags(self, obj):
        tag_count = {}

        for review in obj.reviews.all():
            for review_tag in review.review_tags.all():
                tag_name = review_tag.tag.tag_name

                if tag_name in tag_count:
                    tag_count[tag_name] += 1
                else:
                    tag_count[tag_name] = 1

        top_tags = [k for k, v in sorted(tag_count.items(), key=lambda tag: tag[1], reverse=True)]
        return top_tags[:3]

    class Meta:
        model = Course
        fields = [field.name for field in model._meta.fields]
        fields.extend(['review_count','code_desc', 'tags'])

class ReviewSerializer(serializers.ModelSerializer):
    likes_count = serializers.SerializerMethodField('get_likes_count')
    is_liked = serializers.SerializerMethodField('get_is_liked')
    tags = serializers.SerializerMethodField('get_tags')
    author = serializers.SerializerMethodField('get_author')
    author_generation = serializers.SerializerMethodField('get_author_generation')
    author_study_program = serializers.SerializerMethodField('get_author_study_program')
    course_code = serializers.SerializerMethodField('get_course_code')
    course_code_desc = serializers.SerializerMethodField('get_course_code_desc')
    course_name = serializers.SerializerMethodField('get_course_name')
    course_review_count = serializers.SerializerMethodField('get_course_review_count')

    class Meta:
        model = Review
        fields = [field.name for field in model._meta.fields]
        fields.extend(['author', 'author_generation', 'author_study_program', 'course_code', 'course_code_desc', 'course_name', 
        'course_review_count', 'tags', 'likes_count', 'is_liked'])

    def get_author(self, obj):
        return obj.user.username
    
    def get_author_generation(self, obj):
        generation = 2000 + int(obj.user.npm[:2])
        return str(generation)

    def get_author_study_program(self, obj):
        if "(" not in obj.user.study_program:
            return obj.user.study_program
        return obj.user.study_program.split("(")[0].strip()

    def get_course_code(self, obj):
        return obj.course.code
    
    def get_likes_count(self, obj):
        try:
            review_likes = self.context['review_likes'].filter(review=obj)
        except:
            review_likes = []
        return len(review_likes)
    
    def get_is_liked(self, obj):
        try:
            current_user = self.context['current_user']
            review_likes = self.context['review_likes'].filter(review=obj)
        except:
            review_likes = []

        for like in review_likes:
            if like.user.id == current_user:
                return True

        return False

    def get_tags(self, obj):
        try:
            review_tags = self.context['review_tags'].filter(review=obj)
        except:
            review_tags = []
        tags = []
        for tag in review_tags:
            tags.append(tag.tag.tag_name)
        return tags

    
    def get_course_code_desc(self, obj):
        course_prefixes = get_config('course_prefixes')
        code = obj.course.code[:4]
        if code in course_prefixes:
            return course_prefixes[code]
        return None

    def get_course_name(self, obj):
        return obj.course.name

    def get_course_review_count(self, obj):
        return obj.course.reviews.count()

class ReviewDSSerializer(serializers.ModelSerializer):
    class Meta:
        model = Review
        fields = ('id','content')

class BookmarkSerializer(serializers.ModelSerializer):
    user = serializers.SerializerMethodField('get_user')
    course_code = serializers.SerializerMethodField('get_course_code')
    course_code_desc = serializers.SerializerMethodField('get_course_code_desc')
    course_name = serializers.SerializerMethodField('get_course_name')
    course_review_count = serializers.SerializerMethodField('get_course_review_count')

    class Meta:
        model = Bookmark
        fields = ('user', 'course_code', 'course_code_desc', 'course_name', 'course_review_count')
    
    def get_user(self, obj):
        return obj.user.username
    
    def get_course_code(self, obj):
        return obj.course.code
    
    def get_course_code_desc(self, obj):
        course_prefixes = get_config('course_prefixes')
        code = obj.course.code[:4]
        if code in course_prefixes:
            return course_prefixes[code]
        return None

    def get_course_name(self, obj):
        return obj.course.name

    def get_course_review_count(self, obj):
        return obj.course.reviews.count()

class AccountSerializer(serializers.ModelSerializer):
    term = serializers.SerializerMethodField('get_term')
    generation = serializers.SerializerMethodField('get_generation')

    class Meta:
        model = Profile
        fields = [field.name for field in model._meta.fields]
        fields.extend(['term', 'generation'])

    def get_term(self, obj):
        return get_profile_term(obj)

    def get_generation(self, obj):
        generation = 2000 + int(obj.npm[:2])
        return str(generation)