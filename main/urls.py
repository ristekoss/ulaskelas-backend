from django import conf
from rest_framework import routers
from django.urls import path, include
from .views import CourseViewSet, review, like, get_tags

router = routers.SimpleRouter()
router.register(r"courses", CourseViewSet)

urlpatterns = [
    path("", include(router.urls)),
	path("review", review, name="review"),
	path("like", like, name="like"),
	path("get_tags", get_tags, name="get_tags")
]
