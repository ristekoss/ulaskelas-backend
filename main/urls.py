from django import conf
from rest_framework import routers
from django.urls import path, include

from .views_calculator import calculator, score_component
from .views import like, tag, bookmark, account
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
	path("calculator", calculator, name="calculator"),
	path("score-component", score_component, name="score-component" )
    # path("update_courses", update_courses, name="update_courses"), # temporary
] + router.urls

