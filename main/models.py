from django.db import models
from django.contrib.auth.models import User

# Create your models here.


class Curriculum(models.Model):
    """
    Curriculum of the course.
    """
    name = models.CharField(max_length=31)
    year = models.PositiveSmallIntegerField()


class Tag(models.Model):
    """
    Tags represents some attributes of course, such as:
    * Study program that are required to take this course
        - Ilmu Komputer
        - Sistem Informasi
    * Areas of interest
        - Arsitektur dan Komputasi Awan
        - Teknologi Perangkat Lunak
        - Sains Data & Analitika
        - Kecerdasan Buatan
        - Tata Kelola SI/TI
        - E-Bisnis
        - Ekonomi Digital
    * Others (?)
    """
    name = models.CharField(max_length=31)


class Course(models.Model):
    """
    Mata Kuliah.
    """
    code = models.CharField(max_length=10)
    name = models.CharField(max_length=127)
    aliasName = models.CharField(max_length=63)
    sks = models.PositiveSmallIntegerField()
    description = models.CharField(max_length=127)
    prerequisites = models.ManyToManyField("self", symmetrical=False)
    curriculums = models.ManyToManyField(Curriculum)
    tags = models.ManyToManyField(Tag)


class Profile(models.Model):
    """
    User information generated from SSO UI attributes.
    """
    user = models.OneToOneField(User, on_delete=models.CASCADE)
    name = models.CharField(max_length=63)
    npm = models.CharField(max_length=10)
    role = models.CharField(max_length=31)
    org_code = models.CharField(max_length=11)
    faculty = models.CharField(max_length=63)
    study_program = models.CharField(max_length=63)
    educational_program = models.CharField(max_length=63)
    bookmarked_courses = models.ManyToManyField(Course)

class Review(models.Model):
    """
    Course review from user
    """
    class Semester(models.IntegerChoices):
        GANJIL = 1
        GENAP = 2
        PENDEK = 3
    
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    course = models.ForeignKey(Course, on_delete=models.CASCADE)
    year = models.PositiveSmallIntegerField()
    semester = models.IntegerField(choices=Semester)
    content = models.TextField()