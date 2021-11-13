from django.contrib import admin
from .models import Course, Tag, Profile, Review, ReviewTag

# Register your models here.
admin.site.register(Course)
admin.site.register(Tag)
admin.site.register(Profile)
admin.site.register(Review)
admin.site.register(ReviewTag)
