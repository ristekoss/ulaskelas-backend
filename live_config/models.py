from django.db import models

# Create your models here.
class Configuration(models.Model):
    """
    Live config implementation
    """
    key = models.CharField(max_length=32)
    value = models.TextField()
