from django.db.models import Q
from .models import RoommateProfile, ContactAttempt, CustomUser
from django.contrib.auth import get_user_model, login, authenticate, logout
from django.core.mail import send_mail
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.shortcuts import render, redirect, get_object_or_404
from django_otp.plugins.otp_email.models import EmailDevice
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from .forms import RoommateProfileForm, SharingRequestForm, ContactMessageForm, OTPForm, CustomUserCreationForm, LoginForm, AmenitiesSearchForm, CalculatorForm
from urllib.parse import quote as urlquote, urlparse
from . import services
from .services import CalculatorService, AmenityScoreService
from django.contrib.auth.forms import PasswordResetForm

def _back_with_query(request, default_name="home"):
    ref = request.META.get("HTTP_REFERER")
    if not ref:
        ref = reverse(default_name)
    return ref + ("&" if "?" in ref else "?")

# registration view
def register(request):
    if request.method == "POST":
        form = CustomUserCreationForm(request.POST)
        if form.is_valid():
            user = form.save(commit=False)
            user.is_active = False
            user.save()

            device = EmailDevice.objects.create(user=user, name="default", confirmed=False)
            device.generate_challenge() 

            return redirect("verify_otp", user_id=user.id)

        errs = []
        for field, field_errors in form.errors.items():
            label = "Email" if field == "email" else ("Password" if field.startswith("password") else field.capitalize())
            for e in field_errors:
                errs.append(f"{label}: {e}")
        msg = "Please fix the following:\n" + "\n".join(errs) if errs else "Please check the fields and try again."
        messages.error(request, msg, extra_tags="reg")
        return redirect(_back_with_query(request) + "showRegister=true")

    return redirect(_back_with_query(request) + "showRegister=true")

# view to setup 2FA via email
def send_otp(user):
    device, created = EmailDevice.objects.get_or_create(user=user, name='default')
    device.generate_challenge()

# verify OTP view
User = get_user_model()

def verify_otp(request, user_id):
    user = get_object_or_404(User, pk=user_id)
    device = EmailDevice.objects.filter(user=user, name="default").first()

    # Handle case where device doesn't exist
    if not device:
        messages.error(request, "OTP device not found. Please register again.", extra_tags="otp")
        return redirect("home")

    # Handle resend request
    if request.GET.get("resend") == "1":
        try:
            device.generate_challenge()
            messages.success(request, "A new code has been sent to your email.", extra_tags="otp")
        except Exception as e:
            messages.error(request, "Failed to send OTP. Please try again or register again.", extra_tags="otp")
        return redirect("verify_otp", user_id=user_id)

    if request.method == "POST":
        code = request.POST.get("otp", "").strip()
        if device and device.verify_token(code):
            device.confirmed = True
            device.save()
            user.is_active = True
            user.save()
            login(request, user)
            return redirect("home")
        messages.error(request, "Invalid or expired code. Try again or request a new code.", extra_tags="otp")
        return redirect("verify_otp", user_id=user_id)

    return render(request, "accounts/verify_otp.html", {"user_id": user_id})

# Redirect helpers
_RESET_PATH_SNIPPETS = ("password-reset",)


def _safe_next_url(candidate):
    """Avoid bouncing users back to password reset screens after login."""
    if not candidate:
        return reverse("home")

    parsed = urlparse(candidate)
    target_path = parsed.path or candidate

    if any(snippet in target_path for snippet in _RESET_PATH_SNIPPETS):
        return reverse("home")

    return candidate


# Log in view
def login_view(request):
    if request.method == "POST":
        username = (request.POST.get("username") or "").strip()
        password = request.POST.get("password") or ""

        next_url = (
            request.POST.get("next")
            or request.session.pop("post_login_next", None)
            or reverse("home")
        )
        next_url = _safe_next_url(next_url)

        if not username or not password:
            messages.error(request, "Please enter both email and password.", extra_tags="auth")
            home = reverse("home")
            return redirect(f"{home}?showLogin=true&next={urlquote(next_url)}")

        # Allow users to sign in with either their username or email (older accounts use unique usernames).
        identifier = username
        match = None
        if username:
            match = User.objects.filter(Q(username__iexact=username) | Q(email__iexact=username)).first()
        if match:
            identifier = match.get_username()

        user = authenticate(request, username=identifier, password=password)
        if user is not None:
            login(request, user)
            return redirect(next_url)

        messages.error(request, "Invalid username or password.", extra_tags="auth")
        home = reverse("home")
        return redirect(f"{home}?showLogin=true&next={urlquote(next_url)}")

    next_url = request.GET.get("next") or request.META.get("HTTP_REFERER") or reverse("home")
    next_url = _safe_next_url(next_url)
    request.session["post_login_next"] = next_url  
    home = reverse("home")
    return redirect(f"{home}?showLogin=true&next={urlquote(next_url)}")

# Logout view
def logout_view(request):
    logout(request)
    return redirect("login")  

def password_reset_modal(request):
    if request.method == "POST":
        form = PasswordResetForm(request.POST)
        if form.is_valid():
            email = form.cleaned_data['email']
            associated_users = User.objects.filter(email=email)
            
            if associated_users.exists():
                try:
                    form.save(
                        request=request,
                        use_https=request.is_secure(),
                        subject_template_name="registration/password_reset_subject.txt",
                        email_template_name="registration/password_reset_email.html",
                        from_email=None 
                    )
                    messages.success(
                        request,
                        "Password reset instructions have been sent to your email.",
                        extra_tags="auth"
                    )
                except Exception as e:
                    messages.error(
                        request,
                        "Failed to send password reset email. Please try again.",
                        extra_tags="reset"
                    )
            else:
                # Don't reveal whether a user account exists
                messages.success(
                    request,
                    "If an account exists with that email, we've sent instructions to reset your password.",
                    extra_tags="auth"
                )
            return redirect("password_reset_done")
        else:
            err = form.errors.get("email")
            msg = "Enter a valid email address."
            if err:
                msg = " ".join([e for e in err])
            messages.error(request, msg, extra_tags="reset")
            return redirect("password_reset")

    form = PasswordResetForm()
    return render(request, "accounts/password_reset.html", {"form": form})

# home view
def home(request):
    return render(request, "accounts/home.html")  # render the home page

@login_required
# search for flats within 3km of postal code
def search_flats(request):
    """
    View for searching HDB resale flats by postal code.
    Handles GET requests and renders results.
    """
    postal_code = request.GET.get("q", "").strip()
    
    if not postal_code:
        # No search query - show empty search page
        context = {
            "flats": [],
            "center_lat": 1.3521,
            "center_lng": 103.8198,
            "postal_code": "",
        }
        return render(request, "accounts/search_results.html", context)
    
    # Call service to search flats
    result = services.search_nearby_flats(postal_code, radius_km=3.0)
    
    # Prepare context for template
    context = {
        "flats": result["flats"],
        "center_lat": result["center_lat"],
        "center_lng": result["center_lon"],
        "postal_code": postal_code,
        "postal_towns": result.get("postal_towns", set()),
        "error": result.get("error"),
    }
    
    return render(request, "accounts/search_results.html", context)

@login_required
def roommate_profile_edit(request):
    try:
        profile = RoommateProfile.objects.get(user=request.user)
    except RoommateProfile.DoesNotExist:
        profile = None

    if request.method == 'POST':
        form_data = request.POST.copy()
        
        if profile:
            profile.display_name = form_data.get('display_name')
            profile.age_range = form_data.get('age_range')
            profile.gender = form_data.get('gender')
            profile.race = form_data.get('race') or "-"
            profile.occupation = form_data.get('occupation')
            profile.lifestyle = form_data.get('lifestyle')
            profile.neighbourhoods_csv = form_data.get('neighbourhoods_csv')
            profile.budget = form_data.get('budget')
            profile.save()
        else:
            profile = RoommateProfile.objects.create(
                user=request.user,
                display_name=form_data.get('display_name'),
                age_range=form_data.get('age_range'),
                gender=form_data.get('gender'),
                race=form_data.get('race') or "-",
                occupation=form_data.get('occupation'),
                lifestyle=form_data.get('lifestyle'),
                neighbourhoods_csv=form_data.get('neighbourhoods_csv'),
                budget=form_data.get('budget')
            )

        messages.success(request, 'Profile updated successfully!')
        return redirect('roommate_profile_edit')

    initial_data = {}
    if profile:
        initial_data = {
            'display_name': profile.display_name,
            'age_range': profile.age_range,
            'gender': profile.gender,
            'race': profile.race,
            'occupation': profile.occupation,
            'lifestyle': profile.lifestyle,
            'neighbourhoods_csv': profile.neighbourhoods_csv,
            'budget': profile.budget
        }

    return render(request, 'accounts/roommate_profile_edit.html', {
        'form': {'initial': initial_data}
    })

@login_required
def sharing_request(request):
    results = None
    if request.method == "POST":
        form = SharingRequestForm(request.POST)
        if form.is_valid():
            qs = RoommateProfile.objects.filter(is_looking=True).exclude(user=request.user)

            # Get form data
            min_age = form.cleaned_data.get("min_age")
            max_age = form.cleaned_data.get("max_age")
            gender = form.cleaned_data.get("gender") or ""
            race = form.cleaned_data.get("race") or "-"
            max_budget = form.cleaned_data.get("max_budget")
            n_csv = form.cleaned_data.get("neighbourhoods_csv") or ""
            filter_neigh = {s.strip().lower() for s in n_csv.split(",") if s.strip()}

            # Filter by age_range (convert min/max_age to match age_range strings)
            if min_age or max_age:
                age_ranges = []
                # Map age ranges that match the criteria
                if min_age is None:
                    min_age = 0
                if max_age is None:
                    max_age = 999
                
                # Include ranges that overlap with the requested age range
                if min_age <= 24:
                    age_ranges.append('18-24')
                if min_age <= 34 and max_age >= 25:
                    age_ranges.append('25-34')
                if min_age <= 44 and max_age >= 35:
                    age_ranges.append('35-44')
                if max_age >= 45:
                    age_ranges.append('45+')
                
                if age_ranges:
                    qs = qs.filter(age_range__in=age_ranges)
            
            # Filter by gender
            if gender:
                qs = qs.filter(gender=gender)

            # Filter by race (skip "-" which means no preference)
            if race and race != "-":
                qs = qs.filter(race=race)
            
            # Filter by budget (using 'budget' field, not 'max_budget')
            if max_budget:
                qs = qs.filter(budget__lte=max_budget)

            profiles = list(qs.select_related("user"))
            
            # Filter by neighbourhoods
            if filter_neigh:
                def overlaps(p):
                    if not p.neighbourhoods_csv:
                        return False
                    prefs = [s.strip().lower() for s in p.neighbourhoods_csv.split(",") if s.strip()]
                    return bool(set(prefs).intersection(filter_neigh))
                profiles = [p for p in profiles if overlaps(p)]

            results = profiles
            if not results:
                messages.info(request, "No suitable roommate found based on your filters.")
    else:
        form = SharingRequestForm()

    return render(request, "accounts/sharing_request.html", {"form": form, "results": results})

@login_required
def contact_roommate(request, user_id):
    User = get_user_model()
    recipient = get_object_or_404(User, id=user_id)
    if request.method == "POST":
        form = ContactMessageForm(request.POST)
        if form.is_valid():
            msg = form.cleaned_data["message"]
            ContactAttempt.objects.create(sender=request.user, recipient=recipient, message=msg)
            send_mail(
                subject=f"MyHDBSense: {request.user.username} wants to connect",
                message=msg,
                from_email=None,
                recipient_list=[recipient.email],
                fail_silently=False,
            )
            messages.success(request, "Message sent. Check server console for email (dev mode).")
            return redirect("sharing_request")
    else:
        form = ContactMessageForm()
    return render(request, "accounts/contact_roommate.html", {"form": form, "recipient": recipient})


@login_required
# ------ Amneities Tracker Views ------
def search_amenities(request):
    """
    View for searching amenities by Singapore postal code with validation.
    """
    form = AmenitiesSearchForm(request.GET or None)
    
    context = {
        "amenities": [],
        "center_lat": 1.3521,
        "center_lng": 103.8198,
        "form": form,
        "postal_code": "",
        "score": 0,
        "percentage": 0,
        "score_class": "score--neutral",
    }
    
    # Only process search if form is valid
    if form and form.is_valid():
        postal_code = form.cleaned_data["q"]
        
        # Call service to search amenities
        result = services.search_nearby_amenities(postal_code, radius_km=1.5)
        
        # Add error message if postal code lookup failed
        if result.get("error"):
            messages.error(request, f"Error: {result['error']}")
        
        context.update({
            "amenities": result["amenities"],
            "center_lat": result["center_lat"],
            "center_lng": result["center_lon"],
            "postal_code": postal_code,
            "score": result.get("score", 0),
            "percentage": result.get("percent_score", 0),
            "score_class": result.get("score_class", "score--neutral"),
        })
    
    elif form and not form.is_valid():
        # Form has validation errors - display them
        for field, errors in form.errors.items():
            for error in errors:
                messages.error(request, error)
    
    return render(request, "accounts/amenities.html", context)
                    

@login_required
def amenities(request):
    amenities_data = []  

    total_categories = 14
    found_categories = len({a['type'] for a in amenities_data})
    score = found_categories
    percentage = round((score / total_categories) * 100) if total_categories else 0

    score_class = AmenityScoreService.get_score_class(percentage)

    context = {
        'amenities': amenities_data,
        'score': score,
        'percentage': percentage,   
        'score_class': score_class,
    }
    return render(request, "accounts/amenities.html", context)

@login_required
def properties(request):
    return render(request, 'accounts/properties.html')

@login_required
def calculator(request):
    """
    View for the HDB affordability calculator page.
    Handles both GET (display form) and POST (process calculation) requests.
    """
    form = CalculatorForm()
    results = None
    
    if request.method == "POST":
        form = CalculatorForm(request.POST)
        if form.is_valid():
            # Extract form data
            income = float(form.cleaned_data["income"])
            expenses = float(form.cleaned_data["expenses"])
            cpf_balance = float(form.cleaned_data["cpf_balance"])
            cash_balance = float(form.cleaned_data["cash_balance"])
            property_type = form.cleaned_data["property_type"]
            tenure_years = form.cleaned_data["tenure_years"]
            
            # Calculate affordability using service
            results = CalculatorService.calculate_affordability(
                income=income,
                expenses=expenses,
                cpf_balance=cpf_balance,
                cash_balance=cash_balance,
                property_type=property_type,
                tenure_years=tenure_years
            )
            
            # Add success message
            messages.success(request, "Calculation completed successfully!")
        else:
            # Add error message if form is invalid
            messages.error(request, "Please fix the form errors and try again.")
    
    context = {
        "form": form,
        "results": results,
    }
    
    return render(request, "accounts/calculator.html", context)

@login_required
def roommates(request):
    qs = RoommateProfile.objects.select_related("user").all().order_by("-is_looking", "-id")
    form = SharingRequestForm()
    return render(request, "accounts/roommates.html", {"profiles": qs, "form": form})
