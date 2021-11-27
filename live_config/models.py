from django.db import models

# Create your models here.
class Configuration(models.Model):
    """
    Live config implementation
    """
    key = models.CharField(max_length=32, unique=True, blank=False, null=False)
    value = models.TextField()
