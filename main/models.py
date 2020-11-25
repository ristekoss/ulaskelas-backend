from django.db import models
from django.contrib.auth.models import User

# Create your models here.


class Profile(models.Model):
    '''
    User information generated from SSO UI attributes.
    '''
    user = models.OneToOneField(User, on_delete=models.CASCADE)
    name = models.CharField(max_length=63)
    npm = models.CharField(max_length=10)
    role = models.CharField(max_length=31)
    org_code = models.CharField(max_length=11)
    faculty = models.CharField(max_length=63)
    study_program = models.CharField(max_length=63)
    educational_program = models.CharField(max_length=63)
