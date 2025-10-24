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

class RoommateProfileForm(forms.ModelForm):
    neighbourhoods_csv = forms.CharField(
        required=False,
        label="Preferred neighbourhoods (comma-separated)",
        help_text="e.g., Toa Payoh, Tampines, Punggol",
    )

    class Meta:
        model = RoommateProfile
        fields = ["age", "gender", "race", "max_budget", "is_looking"]
        widgets = {
            "gender": forms.Select(choices=GENDER_CHOICES),
            "race": forms.Select(choices=RACE_CHOICES),
        }

    def clean(self):
        data = super().clean()
        csv = self.data.get("neighbourhoods_csv", "") or self.cleaned_data.get("neighbourhoods_csv", "")
        data["preferred_neighbourhoods"] = [s.strip() for s in csv.split(",") if s.strip()]
        return data

class SharingRequestForm(forms.Form):
    min_age = forms.IntegerField(required=False)
    max_age = forms.IntegerField(required=False)
    gender = forms.ChoiceField(choices=[("", "No preference")] + GENDER_CHOICES, required=False)
    race = forms.ChoiceField(choices=[("-", "No preference")] + RACE_CHOICES, required=False)
    max_budget = forms.IntegerField(required=False, help_text="Your maximum monthly budget (SGD)")
    neighbourhoods_csv = forms.CharField(required=False, help_text="Filter by comma-separated neighbourhoods")

class ContactMessageForm(forms.Form):
    message = forms.CharField(widget=forms.Textarea, max_length=2000, label="Message to send")
