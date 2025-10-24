"""
URL configuration for amenities_tracker project.

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/4.2/topics/http/urls/
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
from . import views

urlpatterns = [
    path('register/', views.register, name='register'), # registration view
    path('verify-otp/<int:user_id>/', views.verify_otp, name='verify_otp'), # OTP verification view
    path('login/', views.login_view, name='login'), # login view
    path('logout/', views.logout_view, name='logout'), # logout view
    path('home/', views.home, name='home'), # home view
    path("search/", views.search_flats, name="search_flats"), # search flats view

    path('roommate/profile/', views.roommate_profile_edit, name='roommate_profile_edit'),
    path('roommate/sharing-request/', views.sharing_request, name='sharing_request'),
    path('roommate/contact/<int:user_id>/', views.contact_roommate, name='contact_roommate'),

]
