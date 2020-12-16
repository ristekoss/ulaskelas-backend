from django.db import models
from django.contrib.auth.models import User

# Create your models here.


class Curriculum(models.Model):
    """
    Curriculum of the course.
    """
    name = models.CharField(max_length=31)
    year = models.PositiveSmallIntegerField()

    def __str__(self):
        return self.name


class Tag(models.Model):
    """
    Tags represents some attributes of course, such as:
    * Study program that are required to take this course
        - Wajib Fakultas
        - Wajib Ilmu Komputer
        - Wajib Sistem Informasi
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

    def __str__(self):
        return self.name

    class Category(models.TextChoices):
        """
        Category of a tag represents relation of the tag to program study.
        This category will translated to color code on the frontend.

        Example:
        Tag Name               | Category | Color
        -------------------------------------------
        Wajib Fakultas         | IK-SI    | Yellow
        Wajib Ilmu Komputer    | IK       | Red
        Wajib Sistem Informasi | SI       | Blue
        Kecerdasan Buatan      | IK       | Red
        E-Bisnis               | SI       | Blue
        """
        FACULTY = 'IK-SI'  # Wajib Fakultas
        CS = 'IK'          # Related to Computer Science / Ilmu Komputer
        IS = 'SI'          # Related to Information System / Sistem Informasi

    category = models.CharField(
        max_length=31, choices=Category.choices,
        default=None, null=True, blank=True)


class Course(models.Model):
    """
    Mata Kuliah.
    """
    code = models.CharField(max_length=10)
    name = models.CharField(max_length=127)
    aliasName = models.CharField(max_length=63)
    sks = models.PositiveSmallIntegerField()
    description = models.CharField(max_length=127, blank=True)
    prerequisites = models.ManyToManyField(
        "self", symmetrical=False, blank=True)
    curriculums = models.ManyToManyField(Curriculum, blank=True)
    tags = models.ManyToManyField(Tag, blank=True)

    def __str__(self):
        return self.name

    def get_category(self):
        if not self.tags.exists():
            return ''
        elif self.tags.filter(name='Wajib Fakultas').exists():
            return Tag.Category.FACULTY.value
        elif self.tags.filter(name='Wajib Ilmu Komputer').exists():
            return Tag.Category.CS.value
        elif self.tags.filter(name='Wajib Sistem Informasi').exists():
            return Tag.Category.IS.value
        # If it's not mandatory course:
        elif self.tags.filter(category=Tag.Category.CS).exists():
            return Tag.Category.CS.value
        elif self.tags.filter(category=Tag.Category.IS).exists():
            return Tag.Category.IS.value
        else:
            return ''


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
    semester = models.IntegerField(choices=Semester.choices)
    content = models.TextField()
