"""UlasKelas URL Configuration

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/3.1/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  path('', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  path('', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.urls import include, path
    2. Add a URL to urlpatterns:  path('blog/', include('blog.urls'))
"""
from django.contrib import admin
from django.urls import path, include
from main import views
from rest_framework.authtoken import views as views_token
# from rest_framework.urlpatterns import format_suffix_patterns
from django.conf import settings # to import static in deployment
from django.conf.urls.static import static # to import static in deployment



urlpatterns = [
    path('admin/', admin.site.urls),
    path('update-course/', views.update_course),
    path('update-leaderboard/', views.update_leaderboard),
    path('ping', views.ping),
    path('health-check', views.health_check),
    path('login/', views.login),
    path('api/', include(("main.urls", "api"), namespace="v1")),
    path('api/v1/', include(("main.urls", "api"), namespace="v1_explicit")),
    path('api/v2/', include(("main.urls", "api"), namespace="v2")),
    path('api-auth-token/', views_token.obtain_auth_token),
    path('token/', views.token, name='token'),
    path('logout/', views.logout),
    # path('api-auth/', include('rest_framework.urls'))
]