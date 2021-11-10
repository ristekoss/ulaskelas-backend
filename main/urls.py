from django import conf
from rest_framework import routers
from django.urls import path, include
from .views import CourseViewSet, review, like, tag, bookmark

router = routers.SimpleRouter()
router.register("courses", CourseViewSet, basename="courses")

urlpatterns = [
    path("", include(router.urls)),
	path("bookmarks", bookmark, name="bookmarks"),
	path("reviews", review, name="reviews"),
	path("likes", like, name="likes"),
	path("tags", tag, name="tags")
    # path("update_courses", update_courses, name="update_courses"), # temporary
] + router.urls

