from django import conf
from rest_framework import routers
from django.urls import path, include
from .views import CourseViewSet, review, like

router = routers.SimpleRouter()
router.register(r"courses", CourseViewSet)

urlpatterns = [
    path("", include(router.urls)),
	path("review", review, name="review"),
	path("like", like, name="like"),
]
