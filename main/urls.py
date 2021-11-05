from django import conf
from rest_framework import routers
from django.urls import path, include
from drf_spectacular.views import SpectacularAPIView, SpectacularSwaggerView
from .views import CourseViewSet, review, like

router = routers.SimpleRouter()
router.register(r"courses", CourseViewSet)

urlpatterns = [
    path("", include(router.urls)),
	path("review", review, name="review"),
	path("like", like, name="like"),
]

# TODO: optimize swagger
if conf.settings.DEBUG:
    urlpatterns += [
        path("schema/", SpectacularAPIView.as_view(), name="schema"),
        path("schema/swagger/", SpectacularSwaggerView.as_view(), name="swagger"),
    ]
