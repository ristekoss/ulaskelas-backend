from django.contrib import admin
from .models import (
    Calculator,
    Course,
    CourseSemester,
    ReviewLike,
    ScoreComponent,
    Tag,
    Profile,
    Review,
    ReviewTag,
    Question,
    Answer,
    QuestionImageAdmin,
    AnswerImageAdmin,
    UserCumulativeGPA,
    UserGPA,
)

# Register your models here.
admin.site.register(Course)
admin.site.register(Tag)
admin.site.register(Profile)

admin.site.register(ReviewLike)
admin.site.register(ReviewTag)
admin.site.register(Calculator)
admin.site.register(ScoreComponent)
admin.site.register(Question, QuestionImageAdmin)
admin.site.register(UserGPA)
admin.site.register(CourseSemester)
admin.site.register(Answer, AnswerImageAdmin)

class ReviewAdmin(admin.ModelAdmin):
    list_display = ("__str__", "is_reviewed", "hate_speech_status", "created_at")
    list_filter = ("is_reviewed", "hate_speech_status", "academic_year", "semester")
    search_fields = ("user__username", "course__name", "course__code")

admin.site.register(Review, ReviewAdmin)
