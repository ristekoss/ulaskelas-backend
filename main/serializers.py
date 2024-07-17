from live_config.views import get_config
from main.utils import get_profile_term
from rest_framework import serializers
from django.db.models import Avg

from .models import Calculator, Course, Profile, Review, ScoreComponent, Tag, Bookmark, UserCumulativeGPA, UserGPA, CourseSemester

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
    rating_understandable = serializers.SerializerMethodField('get_rating_understandable')
    rating_fit_to_credit = serializers.SerializerMethodField('get_rating_fit_to_credit')
    rating_fit_to_study_book = serializers.SerializerMethodField('get_rating_fit_to_study_book')
    rating_beneficial = serializers.SerializerMethodField('get_rating_beneficial')
    rating_recommended = serializers.SerializerMethodField('get_rating_recommended')
    rating_average = serializers.SerializerMethodField('get_rating_average')

    def get_code_desc(self, obj):
        course_prefixes = get_config('course_prefixes')
        code = obj.code[:4]
        if code in course_prefixes:
            return course_prefixes[code]
        return None

    def get_review_count(self, obj):
        return obj.reviews.filter(is_active=True).filter(hate_speech_status='APPROVED').count()
    
    def get_top_tags(self, obj):
        tag_count = {}

        for review in obj.reviews.filter(is_active=True).filter(hate_speech_status='APPROVED').all():
            for review_tag in review.review_tags.all():
                tag_name = review_tag.tag.tag_name

                if tag_name in tag_count:
                    tag_count[tag_name] += 1
                else:
                    tag_count[tag_name] = 1

        top_tags = [k for k, v in sorted(tag_count.items(), key=lambda tag: tag[1], reverse=True)]
        return top_tags[:3]

    def get_all_rating(self, obj):
        obj.ratings = obj.reviews.filter(is_active=True).filter(hate_speech_status='APPROVED').filter(rating_understandable__gte=1).aggregate(
            rating_understandable=Avg('rating_understandable'),
            rating_fit_to_credit=Avg('rating_fit_to_credit'),
            rating_fit_to_study_book=Avg('rating_fit_to_study_book'),
            rating_beneficial=Avg('rating_beneficial'),
            rating_recommended=Avg('rating_recommended')
        )

    def get_rating_understandable(self, obj):
        if not hasattr(obj, 'ratings'):
            self.get_all_rating(obj)
        return obj.ratings.get('rating_understandable') or 0.0

    def get_rating_fit_to_credit(self, obj):
        if not hasattr(obj, 'ratings'):
            self.get_all_rating(obj)
        return obj.ratings.get('rating_fit_to_credit') or 0.0

    def get_rating_fit_to_study_book(self, obj):
        if not hasattr(obj, 'ratings'):
            self.get_all_rating(obj)
        return obj.ratings.get('rating_fit_to_study_book') or 0.0

    def get_rating_beneficial(self, obj):
        if not hasattr(obj, 'ratings'):
            self.get_all_rating(obj)
        return obj.ratings.get('rating_beneficial') or 0.0

    def get_rating_recommended(self, obj):
        if not hasattr(obj, 'ratings'):
            self.get_all_rating(obj)
        return obj.ratings.get('rating_recommended') or 0.0

    def get_rating_average(self, obj):
        if not hasattr(obj, 'ratings'):
            self.get_all_rating(obj)

        rating_total = (obj.ratings.get('rating_understandable') or 0.0)\
            + (obj.ratings.get('rating_fit_to_credit') or 0.0)\
            + (obj.ratings.get('rating_fit_to_study_book') or 0.0)\
            + (obj.ratings.get('rating_beneficial') or 0.0)\
            + (obj.ratings.get('rating_recommended') or 0.0)

        return rating_total / 5.0

    class Meta:
        model = Course
        fields = [field.name for field in model._meta.fields]
        fields.extend(['review_count','code_desc', 'tags', 'rating_understandable', 'rating_fit_to_credit',
        'rating_fit_to_study_book', 'rating_beneficial', 'rating_recommended', 'rating_average'])

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
    rating_average = serializers.SerializerMethodField('get_rating_average')

    class Meta:
        model = Review
        fields = [field.name for field in model._meta.fields]
        fields.extend(['author', 'author_generation', 'author_study_program', 'course_code', 'course_code_desc', 'course_name', 
        'course_review_count', 'tags', 'likes_count', 'is_liked', 'rating_average'])

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
        return obj.course.reviews.filter(is_active=True).filter(hate_speech_status='APPROVED').count()

    def get_rating_average(self, obj):
        return ((obj.rating_understandable or 0) + (obj.rating_fit_to_credit or 0) + (obj.rating_fit_to_study_book or 0) + (obj.rating_beneficial or 0) + (obj.rating_recommended or 0)) / 5

class ReviewDSSerializer(serializers.ModelSerializer):
    class Meta:
        model = Review
        fields = ('id','content')

class BookmarkSerializer(serializers.ModelSerializer):
    user = serializers.SerializerMethodField('get_user')
    course_id = serializers.SerializerMethodField('get_course_id')
    course_code = serializers.SerializerMethodField('get_course_code')
    course_code_desc = serializers.SerializerMethodField('get_course_code_desc')
    course_name = serializers.SerializerMethodField('get_course_name')
    course_review_count = serializers.SerializerMethodField('get_course_review_count')

    class Meta:
        model = Bookmark
        fields = ('user', 'course_id', 'course_code', 'course_code_desc', 'course_name', 'course_review_count')
    
    def get_user(self, obj):
        return obj.user.username
    
    def get_course_id(self, obj):
        return obj.course.id

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
        return obj.course.reviews.filter(is_active=True).filter(hate_speech_status='APPROVED').count()

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

class CalculatorSerializer(serializers.ModelSerializer):
    user = serializers.SerializerMethodField('get_user')
    course_id = serializers.SerializerMethodField('get_course_id')
    course_name = serializers.SerializerMethodField('get_course_name')

    class Meta:
        model = Calculator
        fields = ('id', 'user', 'course_id', 'course_name', 'total_score', "total_percentage")

    def get_user(self, obj):
        return obj.user.username

    def get_course_id(self, obj):
        return obj.course.id

    def get_course_name(self, obj):
        return obj.course.name

class ScoreComponentSerializer(serializers.ModelSerializer):
    calculator_id = serializers.SerializerMethodField('get_calculator_id')
    
    class Meta:
        model = ScoreComponent
        fields = ('id', 'calculator_id', 'name', 'weight', 'score')

    def get_calculator_id(self, obj):
        return obj.calculator.id
    
class UserCumulativeGPASerializer(serializers.ModelSerializer):
    user = serializers.SerializerMethodField('get_user')
    class Meta:
        model = UserCumulativeGPA
        fields = ('user', 'cumulative_gpa', 'total_gpa', 'total_sks')
    
    def get_user(self, obj):
        return obj.user.username
    
class UserGPASerializer(serializers.ModelSerializer):
    pk = serializers.IntegerField(read_only=True)
    class Meta:
        model = UserGPA
        fields = ('pk', 'given_semester', 'total_sks', 'semester_gpa', 'semester_mutu')

class CourseSemesterSerializer(serializers.ModelSerializer):
    pk = serializers.IntegerField(read_only=True)
    semester = serializers.SerializerMethodField('get_semester')
    course = CourseSerializer()
    class Meta:
        model = CourseSemester
        fields = ('pk', 'semester', 'course')

    def get_semester(self, obj):
        return obj.semester.given_semester
    
class CourseForSemesterSerializer(serializers.ModelSerializer):
    class Meta:
        model = Course
        fields = ['id', 'name']

class SemesterWithCourseSerializer(serializers.ModelSerializer):
    semester = serializers.SerializerMethodField('get_semester')
    courses_calculator = serializers.SerializerMethodField('get_courses_calculator')

    class Meta:
        model = UserGPA
        fields = ['semester', 'courses_calculator']

    def get_courses_calculator(self, obj):
        list_courses = CourseSemester.objects.filter(semester=obj)
        list_courses = [course_semester.course for course_semester in list_courses]
        list_calculator = [
            CourseSemester.objects.filter(semester=obj, course=course).first().calculator 
            for course in list_courses
        ]
        return CalculatorSerializer(list_calculator, many=True).data
    
    def get_semester(self, obj):
        return UserGPASerializer(obj).data