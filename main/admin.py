from django.contrib import admin
from .models import Calculator, Course, ReviewLike, ScoreComponent, Tag, Profile, Review, ReviewTag, Question, Answer, QuestionImageAdmin, AnswerImageAdmin

# Register your models here.
admin.site.register(Course)
admin.site.register(Tag)
admin.site.register(Profile)
admin.site.register(Review)
admin.site.register(ReviewLike)
admin.site.register(ReviewTag)
admin.site.register(Calculator)
admin.site.register(ScoreComponent)
admin.site.register(Question, QuestionImageAdmin)
admin.site.register(Answer, AnswerImageAdmin)