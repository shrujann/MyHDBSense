from django import forms
from django.contrib.auth.forms import UserCreationForm
from .models import CustomUser


class OTPForm(forms.Form):
    otp = forms.CharField(label="Enter OTP", max_length=6)

class CustomUserCreationForm(UserCreationForm):
    class Meta(UserCreationForm):
        model = CustomUser
        fields = ("username", "email")

class LoginForm(forms.Form):
    username = forms.CharField(label="Username", max_length=150)
    password = forms.CharField(label="Password", widget=forms.PasswordInput)