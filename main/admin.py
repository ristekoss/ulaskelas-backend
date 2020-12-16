from django.contrib import admin
from .models import Course, Curriculum, Tag

# Register your models here.
admin.site.register(Course)
admin.site.register(Curriculum)
admin.site.register(Tag)
