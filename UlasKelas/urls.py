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


urlpatterns = [
    path('admin/', admin.site.urls),
    path('sample/', views.sample_api),
    path('ping', views.ping),
    path('sample-restricted/', views.restricted_sample_endpoint),
    path('login/', views.login),
    path('api/', include("main.urls")),
    path('api-auth-token/', views_token.obtain_auth_token),
    path('token/', views.token, name='token'),
    path('logout/', views.logout),
    # path('api-auth/', include('rest_framework.urls'))
]
