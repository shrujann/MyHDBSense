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
from django.contrib.auth import views as auth_views

urlpatterns = [
    path('register/', views.register, name='register'), # registration view
    path('verify-otp/<int:user_id>/', views.verify_otp, name='verify_otp'), # OTP verification view
    path('login/', views.login_view, name='login'), # login view
    path('logout/', views.logout_view, name='logout'), # logout view

    path('password-reset/', auth_views.PasswordResetView.as_view(template_name='accounts/password_reset.html'), name='password_reset'), 
    path('password-reset/done/', auth_views.PasswordResetDoneView.as_view(template_name='accounts/password_reset_done.html'), name='password_reset_done'),
    path('password-reset-confirm/<uidb64>/<token>/', auth_views.PasswordResetConfirmView.as_view(template_name='accounts/password_reset_confirm.html'), name='password_reset_confirm'),   
    path('password-reset-complete/', auth_views.PasswordResetCompleteView.as_view(template_name='accounts/password_reset_complete.html'), name='password_reset_complete'),

    path('home/', views.home, name='home'), # home view

    path('properties/', views.properties, name='properties'), # properties listing view
    path("search/", views.search_flats, name="search_flats"), # search flats view
    path('search-amenities/', views.search_amenities, name='search_amenities'), 
    path('amenities/', views.amenities, name='amenities'), # amenities view
    path('calculator/', views.calculator, name='calculator'), # HDB affordability calculator view

    path('roommate/profile/', views.roommate_profile_edit, name='roommate_profile_edit'),
    path('roommate/sharing-request/', views.sharing_request, name='sharing_request'),
    path('roommate/contact/<int:user_id>/', views.contact_roommate, name='contact_roommate'),
    path('roommates/', views.roommates, name='roommates'), # roommates listing view
]
