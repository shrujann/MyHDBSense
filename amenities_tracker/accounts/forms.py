from django import forms
from django.contrib.auth.forms import UserCreationForm
from .models import CustomUser
from .models import RoommateProfile, GENDER_CHOICES, RACE_CHOICES
import re


class OTPForm(forms.Form):
    otp = forms.CharField(label="Enter OTP", max_length=6)

class CustomUserCreationForm(UserCreationForm):
    class Meta(UserCreationForm):
        model = CustomUser
        fields = ("username", "email")

class LoginForm(forms.Form):
    username = forms.CharField(label="Username", max_length=150)
    password = forms.CharField(label="Password", widget=forms.PasswordInput)

def validate_singapore_postal_code(postal_code):
    """
    Validate Singapore postal code format and sector.
    
    Singapore postal codes:
    - Must be exactly 6 digits
    - First 2 digits (sector) must be 01-82 (valid postal sectors in Singapore)
    
    Returns: cleaned postal code or raises ValidationError
    """
    # Remove any spaces and convert to string
    postal_code = str(postal_code).strip().replace(' ', '')
    
    # Check if it's exactly 6 digits
    if not re.match(r'^\d{6}$', postal_code):
        raise forms.ValidationError(
            "Please enter a valid Singapore postal code (6 digits, e.g., 310190)."
        )
    
    # Extract the sector (first 2 digits)
    sector = int(postal_code[:2])
    
    # Valid Singapore postal sectors range from 01 to 82
    if not (1 <= sector <= 82):
        raise forms.ValidationError(
            "Please enter a valid Singapore postal code. "
            "The postal sector (first 2 digits) must be between 01 and 82."
        )
    
    return postal_code

class AmenitiesSearchForm(forms.Form):
    """
    Form for searching amenities by Singapore postal code.
    Includes validation for proper Singapore postal code format.
    """
    q = forms.CharField(
        label="Postal Code",
        max_length=6,
        widget=forms.TextInput(attrs={
            'placeholder': 'e.g. 310190',
            'class': 'form-control',
            'pattern': '[0-9]{6}',
            'title': 'Please enter a 6-digit Singapore postal code'
        }),
        help_text="Enter a valid 6-digit Singapore postal code"
    )
    
    def clean_q(self):
        postal_code = self.cleaned_data.get('q')
        if postal_code:
            return validate_singapore_postal_code(postal_code)
        return postal_code

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

        csv = self.data.get("neighbourhoods_csv", "") or data.get("neighbourhoods_csv", "")
        raw_items = [s.strip() for s in csv.split(",") if s.strip()]

        canon_map = {n.lower(): n for n in VALID_NEIGHBOURHOODS}

        invalid = [s for s in raw_items if s.lower() not in canon_map]
        if invalid:
            raise forms.ValidationError("Invalid neighbourhood input.")

        data["preferred_neighbourhoods"] = [canon_map[s.lower()] for s in raw_items]
        return data

VALID_NEIGHBOURHOODS = {
    "Ang Mo Kio","Bedok","Bishan","Bukit Batok","Bukit Merah","Bukit Panjang","Bukit Timah",
    "Central Area","Choa Chu Kang","Clementi","Geylang","Hougang","Jurong East","Jurong West",
    "Kallang/Whampoa","Marine Parade","Novena","Pasir Ris","Punggol","Queenstown","Sembawang",
    "Sengkang","Serangoon","Tampines","Toa Payoh","Woodlands","Yishun"
}

class SharingRequestForm(forms.Form):
    min_age = forms.IntegerField(required=False)
    max_age = forms.IntegerField(required=False)
    gender = forms.ChoiceField(choices=[("", "No preference")] + GENDER_CHOICES, required=False)
    race = forms.ChoiceField(choices=[("-", "No preference")] + RACE_CHOICES, required=False)
    max_budget = forms.IntegerField(required=False, help_text="Your maximum monthly budget (SGD)")
    neighbourhoods_csv = forms.CharField(required=False, help_text="Filter by comma-separated neighbourhoods")

class ContactMessageForm(forms.Form):
    message = forms.CharField(widget=forms.Textarea, max_length=2000, label="Message to send")
