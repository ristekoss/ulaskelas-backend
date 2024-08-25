import mimetypes
from django.contrib.auth.models import User
from django.db import models
from django.db.models.deletion import CASCADE
from django.db.models import UniqueConstraint
from django.contrib.contenttypes.models import ContentType
from django.contrib.contenttypes.fields import GenericForeignKey
import boto3
import environ

from django.utils import timezone
from django.utils.html import format_html
from django.contrib import admin

env = environ.Env()
expires_in = 60*60*7 # 7 Hours

class Tag(models.Model):
    """
    Tag for a review
    """
    tag_name = models.CharField(max_length=30)
    is_active = models.BooleanField(default=True)

    def __str__(self):
        return self.tag_name

class Course(models.Model):
    """
    Mata Kuliah.
    """
    code = models.CharField(max_length=10)
    curriculum = models.CharField(max_length=20)
    name = models.CharField(max_length=127)
    description = models.CharField(max_length=2048, blank=True)
    sks = models.PositiveSmallIntegerField()
    term = models.PositiveSmallIntegerField()
    prerequisites = models.CharField(max_length=512, blank=True)

    def __str__(self):
        return self.name

class Profile(models.Model):
    """
    User information generated from SSO UI attributes.
    """
    user = models.ForeignKey(User, on_delete=models.SET_NULL, null=True)
    username = models.CharField(max_length=63)
    name = models.CharField(max_length=63)
    npm = models.CharField(max_length=10)
    faculty = models.CharField(max_length=63)
    study_program = models.CharField(max_length=63)
    educational_program = models.CharField(max_length=63)
    role = models.CharField(max_length=63)
    org_code = models.CharField(max_length=63)
    is_blocked = models.BooleanField(default=False)
    likes_count = models.PositiveIntegerField(default=0, null=True)

class Review(models.Model):
    """
    Course review from user
    """
    class Semester(models.IntegerChoices):
        GANJIL = 1
        GENAP = 2

    class HateSpeechStatus(models.TextChoices):
        WAITING = 'WAITING'
        APPROVED = 'APPROVED'
        REJECTED = 'REJECTED'

    user = models.ForeignKey(Profile, on_delete=models.SET_NULL, null=True)
    course = models.ForeignKey(Course, on_delete=models.CASCADE, related_name='reviews')
    created_at = models.DateTimeField()
    updated_at = models.DateTimeField()
    academic_year = models.CharField(max_length=9)
    semester = models.IntegerField(choices=Semester.choices)
    content = models.TextField()
    hate_speech_status = models.CharField(choices=HateSpeechStatus.choices, max_length=20)
    sentimen = models.PositiveSmallIntegerField(null=True)
    is_anonym = models.BooleanField(default=False)
    is_active = models.BooleanField(default=True)
    is_reviewed = models.BooleanField(default=False)
    rating_understandable = models.FloatField(null=True, default=0)
    rating_fit_to_credit = models.FloatField(null=True, default=0)
    rating_fit_to_study_book = models.FloatField(null=True, default=0)
    rating_beneficial = models.FloatField(null=True, default=0)
    rating_recommended = models.FloatField(null=True, default=0)

    def save(self, *args, **kwargs):
        ''' On save, update timestamps '''
        if not self.id:
            self.created_at = timezone.now()
            self.hate_speech_status = "WAITING"
        self.updated_at = timezone.now()
        return super(Review, self).save(*args, **kwargs)

class ReviewLike(models.Model):
    user = models.ForeignKey(Profile, on_delete=CASCADE)
    review = models.ForeignKey(Review, on_delete=CASCADE)

class ReviewTag(models.Model):
    review = models.ForeignKey(Review, on_delete=CASCADE, related_name='review_tags')
    tag = models.ForeignKey(Tag, on_delete=CASCADE)

class Bookmark(models.Model):
    """
    Bookmark course for a profile
    """
    user = models.ForeignKey(Profile, on_delete=CASCADE)
    course = models.ForeignKey(Course, on_delete=CASCADE)

class Calculator(models.Model):
    """
    Calculator for course score
    """
    user = models.ForeignKey(Profile, on_delete=CASCADE)
    course = models.ForeignKey(Course, on_delete=CASCADE)
    total_score = models.FloatField(default=0)
    total_percentage = models.FloatField(default=0)

class ScoreComponent(models.Model):
    """
    Score component for calculator
    """
    calculator = models.ForeignKey(Calculator, on_delete=CASCADE)
    name = models.TextField()
    weight = models.FloatField()
    score = models.FloatField()
    
class UserCumulativeGPA(models.Model):
    """
    User's Cumulative GPA/IPK (Indeks Prestasi Kumulatif)
    """
    user = models.ForeignKey(Profile, on_delete=CASCADE)
    cumulative_gpa = models.FloatField(default=0)
    total_gpa = models.FloatField(default=0)
    total_sks = models.PositiveIntegerField(default=0)

class UserGPA(models.Model):
    """
    User's GPA/IP (Indeks Prestasi) for the given semester
    Note that mutu = sum(sks * nilai) for every course in the given_semester
    """
    userCumulativeGPA = models.ForeignKey(UserCumulativeGPA, on_delete=CASCADE)
    given_semester = models.CharField(max_length=20)
    total_sks = models.PositiveIntegerField(default=0)
    semester_gpa = models.FloatField(default=0)
    semester_mutu = models.FloatField(default=0)

    class Meta:
        constraints = [
            UniqueConstraint(fields=['userCumulativeGPA', 'given_semester'], name='unique_userCumulativeGPA_given_semester')
        ]

class CourseSemester(models.Model):
    """
    This class tells what course(s) are taken in a semester
    """
    semester = models.ForeignKey(UserGPA, on_delete=CASCADE)
    course = models.ForeignKey(Course, on_delete=CASCADE)
    calculator = models.ForeignKey(Calculator, on_delete=CASCADE, null=True)

    class Meta:
        constraints = [
            UniqueConstraint(fields=['semester', 'course'], name='unique_semester_course')
        ]

class ScoreSubcomponent(models.Model):
    """
    This class describes the subcomponent from a score component
    Ex: There is a Quiz Component, so the subcomponent might be:
    - Quiz 1
    - Quiz 2
    - Quiz 3
    - ...etc
    """
    score_component = models.ForeignKey(ScoreComponent, on_delete=CASCADE)
    subcomponent_number = models.PositiveIntegerField()
    subcomponent_score = models.FloatField(null=True)

    class Meta:
        constraints = [
            UniqueConstraint(fields=['score_component', 'subcomponent_number'], name='unique_number')
        ]

class Question(models.Model):
    """
    This class represent the Question model for "TanyaTeman" Feature
    is_anonym = 1 if the user wants to be anonym in the question, otherwise is_anonym = 0
    """

    class VerificationStatus(models.TextChoices):
        WAITING = "Menunggu Verifikasi"
        APPROVED = "Terverifikasi"

    user = models.ForeignKey(Profile, on_delete=CASCADE)
    question_text = models.TextField()
    course = models.ForeignKey(Course, on_delete=CASCADE)
    is_anonym = models.IntegerField()
    attachment = models.CharField(null=True, max_length=120)
    like_count = models.IntegerField(default=0)
    reply_count = models.IntegerField(default=0)
    verification_status = models.TextField(choices=VerificationStatus.choices, default=VerificationStatus.WAITING)
    created_at = models.DateTimeField(default=timezone.now)
    
class Answer(models.Model):
    """
    This class represent the Answer/Reply for the Question
    is_anonym = 1 if the user wants to be anonym in the question, otherwise is_anonym = 0
    """

    class VerificationStatus(models.TextChoices):
        WAITING = "Menunggu Verifikasi"
        APPROVED = "Terverifikasi"

    user = models.ForeignKey(Profile, on_delete=CASCADE)
    question = models.ForeignKey(Question, on_delete=CASCADE)
    answer_text = models.TextField()
    is_anonym = models.IntegerField()
    attachment = models.CharField(null=True, max_length=120)
    like_count = models.IntegerField(default=0)
    verification_status = models.TextField(choices=VerificationStatus.choices, default=VerificationStatus.WAITING)
    created_at = models.DateTimeField(default=timezone.now)


def get_attachment_presigned_url(attachment, expires_in=expires_in):
    if attachment is None:
        return attachment

    s3 = boto3.client(
        's3', 
        aws_access_key_id=env("ACCESS_KEY_ID"), 
        aws_secret_access_key=env("ACCESS_KEY_SECRET"), 
        region_name=env("AWS_REGION")
    )

    attachment_type = attachment.split('.')[-1]

    url = s3.generate_presigned_url(
        'get_object',
        Params={
            'Bucket': env("BUCKET_NAME"),
            'Key': attachment,
            'ResponseContentDisposition': 'inline',
            'ResponseContentType': attachment_type
        },
        ExpiresIn=expires_in
    )
    return url

class LikePost(models.Model):
    """
    This class That a user like a Post (Could be Question/Answer)
    """
    user = models.ForeignKey(Profile, on_delete=models.CASCADE)
    content_type = models.ForeignKey(ContentType, on_delete=models.CASCADE)
    object_id = models.PositiveIntegerField()
    content_object = GenericForeignKey('content_type', 'object_id')

    class Meta:
        unique_together = ('user', 'content_type', 'object_id')

    def __str__(self):
        return f'{self.user.username} liked {self.content_object}: {self.content_type} {self.object_id}'

class QuestionImageAdmin(admin.ModelAdmin):
    def image_tag(self, obj):
        return format_html('<img src="{}" style="max-width:200px; max-height:200px"/>'.format(get_attachment_presigned_url(obj.attachment)))

    list_display = ['question_text','image_tag',]

class AnswerImageAdmin(admin.ModelAdmin):
    def image_tag(self, obj):
        return format_html('<img src="{}" style="max-width:200px; max-height:200px"/>'.format(get_attachment_presigned_url(obj.attachment)))

    list_display = ['answer_text','image_tag',]