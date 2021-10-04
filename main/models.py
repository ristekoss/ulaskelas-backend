from django.db import models
from django.db.models.deletion import CASCADE

from django.utils import timezone

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
    credit = models.PositiveSmallIntegerField()
    prerequisite_course = models.ManyToManyField("self", blank=True)

    def __str__(self):
        return self.name

class Profile(models.Model):
    """
    User information generated from SSO UI attributes.
    """
    username = models.CharField(max_length=63)
    name = models.CharField(max_length=63)
    npm = models.CharField(max_length=10)
    faculty = models.CharField(max_length=63)
    study_program = models.CharField(max_length=63)


class Review(models.Model):
    """
    Course review from user
    """
    class Semester(models.IntegerChoices):
        GANJIL = 1
        GENAP = 2

    class HateSpeechStatus(models.TextChoices):
        WAITING = 'WAITING'
        VERIFIED = 'VERIFIED'

    user = models.ForeignKey(Profile, on_delete=models.SET_NULL, null=True)
    course = models.ForeignKey(Course, on_delete=models.CASCADE)
    created_at = models.DateTimeField()
    updated_at = models.DateTimeField()
    academic_year = models.PositiveIntegerField()
    semester = models.IntegerField(choices=Semester.choices)
    content = models.TextField()
    hate_speech_status = models.CharField(choices=HateSpeechStatus.choices, max_length=20)
    sentimen = models.PositiveSmallIntegerField()
    is_anonym = models.BooleanField(default=False)

    def save(self, *args, **kwargs):
        ''' On save, update timestamps '''
        if not self.id:
            self.created = timezone.now()
        self.modified = timezone.now()
        return super(Review, self).save(*args, **kwargs)


class ReviewLike(models.Model):
    user = models.ForeignKey(Profile, on_delete=CASCADE)
    review = models.ForeignKey(Review, on_delete=CASCADE)


class Bookmark(models.Model):
    """
    Bookmark course for a profile
    """
    user = models.ForeignKey(Profile, on_delete=CASCADE)
    course = models.ForeignKey(Course, on_delete=CASCADE)

