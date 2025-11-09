from django import forms
from django.contrib.auth.forms import UserCreationForm, PasswordResetForm
from django.contrib.auth import get_user_model
from .models import CustomUser, RoommateProfile
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
    class Meta:
        model = RoommateProfile
        fields = [
            'display_name',
            'age_range',
            'gender',
            'occupation',
            'lifestyle',
            'neighbourhoods_csv',
            'budget'
        ]
        widgets = {
            'display_name': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Your display name'
            }),
            'age_range': forms.Select(attrs={'class': 'form-select'}),
            'gender': forms.Select(attrs={'class': 'form-select'}),
            'occupation': forms.Select(attrs={'class': 'form-select'}),
            'lifestyle': forms.Select(attrs={'class': 'form-select'}),
            'budget': forms.NumberInput(attrs={
                'placeholder': 'e.g. 800',
                'class': 'form-control'
            }),
            'neighbourhoods_csv': forms.TextInput(attrs={
                'placeholder': 'e.g. Tampines, Pasir Ris, Bedok',
                'class': 'form-control'
            })
        }

    def clean(self):
        data = super().clean()
        csv = self.data.get("neighbourhoods_csv", "") or data.get("neighbourhoods_csv", "")
        raw_items = [s.strip() for s in csv.split(",") if s.strip()]
        
        canon_map = {n.lower(): n for n in VALID_NEIGHBOURHOODS}
        invalid = [s for s in raw_items if s.lower() not in canon_map]
        
        if invalid:
            raise forms.ValidationError(f"Invalid neighbourhoods: {', '.join(invalid)}")
        
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

class CalculatorForm(forms.Form):
    """
    Form for HDB affordability calculator inputs
    """
    income = forms.DecimalField(
        label="Monthly Gross Income (SGD)",
        max_digits=10,
        decimal_places=2,
        min_value=0,
        widget=forms.NumberInput(attrs={
            'placeholder': 'e.g. 6000',
            'class': 'form-control',
            'step': '0.01'
        })
    )
    
    expenses = forms.DecimalField(
        label="Monthly Expenses (SGD)",
        max_digits=10,
        decimal_places=2,
        min_value=0,
        widget=forms.NumberInput(attrs={
            'placeholder': 'e.g. 2000',
            'class': 'form-control',
            'step': '0.01'
        })
    )
    
    cpf_balance = forms.DecimalField(
        label="CPF OA Balance (SGD)",
        max_digits=12,
        decimal_places=2,
        min_value=0,
        widget=forms.NumberInput(attrs={
            'placeholder': 'e.g. 80000',
            'class': 'form-control',
            'step': '0.01'
        }),
        help_text="Can be used for down payment and monthly servicing"
    )
    
    cash_balance = forms.DecimalField(
        label="Cash Available for Down Payment (SGD)",
        max_digits=12,
        decimal_places=2,
        min_value=0,
        widget=forms.NumberInput(attrs={
            'placeholder': 'e.g. 50000',
            'class': 'form-control',
            'step': '0.01'
        })
    )
    
    property_type = forms.ChoiceField(
        label="Property Type",
        choices=[
            ('HDB_20', 'HDB (20% down payment)'),
            ('BANK_25', 'Bank Loan (25% down payment)')
        ],
        initial='HDB_20',
        widget=forms.Select(attrs={'class': 'form-select'})
    )
    
    tenure_years = forms.IntegerField(
        label="Loan Tenure (Years)",
        min_value=5,
        max_value=30,
        initial=25,
        widget=forms.NumberInput(attrs={
            'class': 'form-control',
            'min': '5',
            'max': '30'
        })
    )


class EmailLookupPasswordResetForm(PasswordResetForm):
    """
    Enforces that the submitted email belongs to a registered user before sending reset instructions.
    """
    def clean_email(self):
        email = (self.cleaned_data.get("email") or "").strip()
        UserModel = get_user_model()
        if not email or not UserModel.objects.filter(email__iexact=email).exists():
            raise forms.ValidationError("Email does not exist")
        return email
