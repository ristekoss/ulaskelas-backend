from django import conf
from rest_framework import routers
from django.urls import path, include
from .views_gpa_calculator import gpa_calculator, gpa_calculator_with_semester
from .views_calculator import calculator, score_component
from .views import like, tag, bookmark, account, leaderboard
from .views_review import ds_review, review
from .views_course import CourseViewSet

router = routers.SimpleRouter()
router.register("courses", CourseViewSet, basename="courses")

urlpatterns = [
    path("", include(router.urls)),
	path("bookmarks", bookmark, name="bookmarks"),
	path("reviews", review, name="reviews"),
	path("ds-reviews", ds_review, name="ds-reviews"),
	path("likes", like, name="likes"),
	path("tags", tag, name="tags"),
	path("account", account, name="account"),
	path("leaderboard", leaderboard, name="leaderboard"),
	path("calculator", calculator, name="calculator"),
	path("score-component", score_component, name="score-component"),
  path("calculator-gpa", gpa_calculator, name="gpa-calculator"),
  path('calculator-gpa/<str:given_semester>', gpa_calculator_with_semester, name="gpa-calculator-with-semester")
] + router.urls

