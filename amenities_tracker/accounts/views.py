from django.db.models import Q
from .models import RoommateProfile, ContactAttempt, CustomUser
from django.contrib.auth import get_user_model, login
from django.core.mail import send_mail
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth import login, authenticate, logout
from django_otp.plugins.otp_email.models import EmailDevice
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from .forms import RoommateProfileForm, SharingRequestForm, ContactMessageForm, OTPForm, CustomUserCreationForm, LoginForm
from .models import CustomUser
from urllib.parse import quote as urlquote, urlparse
from . import services

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

    # resend
    if request.GET.get("resend") == "1" and device:
        device.generate_challenge()
        messages.success(request, "A new code was sent to your email.", extra_tags="otp")
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
        messages.error(request, "Invalid or expired code. Try again.", extra_tags="otp")
        return redirect("verify_otp", user_id=user_id)

    return render(request, "accounts/verify_otp.html", {"user_id": user_id})

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

        if not username or not password:
            messages.error(request, "Please enter both email and password.", extra_tags="auth")
            home = reverse("home")
            return redirect(f"{home}?showLogin=true&next={urlquote(next_url)}")

        user = authenticate(request, username=username, password=password)
        if user is not None:
            login(request, user)
            return redirect(next_url)

        messages.error(request, "Invalid username or password.", extra_tags="auth")
        home = reverse("home")
        return redirect(f"{home}?showLogin=true&next={urlquote(next_url)}")

    next_url = request.GET.get("next") or request.META.get("HTTP_REFERER") or reverse("home")
    request.session["post_login_next"] = next_url  
    home = reverse("home")
    return redirect(f"{home}?showLogin=true&next={urlquote(next_url)}")

# Logout view
def logout_view(request):
    logout(request)
    return redirect("login")  # Redirect to login page after logout

def password_reset_modal(request):
    if request.method == "POST":
        form = PasswordResetForm(request.POST)
        if form.is_valid():
            # Sends email if account with that email exists.
            form.save(
                request=request,
                use_https=request.is_secure(),
                email_template_name="registration/password_reset_email.html",  
            )
            messages.success(
                request,
                "If an account exists with that email, we’ve sent instructions to reset your password.",
                extra_tags="auth" 
            )
            return redirect(_back_with_query(request) + "showLogin=true")
        else:
            err = form.errors.get("email")
            msg = "Enter a valid email address."
            if err:
                msg = " ".join([e for e in err])
            messages.error(request, msg, extra_tags="reset")
            return redirect(_back_with_query(request) + "showReset=true")

    return redirect(_back_with_query(request) + "showReset=true")

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
    profile, _ = RoommateProfile.objects.get_or_create(user=request.user)
    if request.method == "POST":
        form = RoommateProfileForm(request.POST, instance=profile)
        if form.is_valid():
            p = form.save(commit=False)
            p.preferred_neighbourhoods = form.cleaned_data.get("preferred_neighbourhoods", [])
            p.save()
            messages.success(request, "Roommate profile updated.")
            return redirect("roommate_profile_edit")
    else:
        initial_csv = ", ".join(profile.preferred_neighbourhoods or [])
        form = RoommateProfileForm(instance=profile, initial={"neighbourhoods_csv": initial_csv})
    return render(request, "accounts/roommate_profile_edit.html", {"form": form})

@login_required
def sharing_request(request):
    results = None
    if request.method == "POST":
        form = SharingRequestForm(request.POST)
        if form.is_valid():
            qs = RoommateProfile.objects.filter(is_looking=True).exclude(user=request.user)

            min_age = form.cleaned_data.get("min_age")
            max_age = form.cleaned_data.get("max_age")
            gender = form.cleaned_data.get("gender") or ""
            race = form.cleaned_data.get("race") or "-"
            max_budget = form.cleaned_data.get("max_budget")
            n_csv = form.cleaned_data.get("neighbourhoods_csv") or ""
            filter_neigh = {s.strip().lower() for s in n_csv.split(",") if s.strip()}

            if min_age: qs = qs.filter(age__gte=min_age)
            if max_age: qs = qs.filter(age__lte=max_age)
            if gender:  qs = qs.filter(gender=gender)
            if race and race != "-": qs = qs.filter(race=race)
            if max_budget: qs = qs.filter(Q(max_budget__isnull=True) | Q(max_budget__lte=max_budget))

            profiles = list(qs.select_related("user"))
            if filter_neigh:
                def overlaps(p):
                    prefs = [s.lower() for s in (p.preferred_neighbourhoods or [])]
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
    postal_code = request.GET.get("q", "").strip()
    filter_type = request.GET.get("type", "").strip()  # Optional filter
    
    if not postal_code:
        context = {
            "amenities": [],
            "center_lat": 1.3521,
            "center_lng": 103.8198,
        }
        return render(request, "accounts/amenities_results.html", context)
    
    result = services.search_nearby_amenities(postal_code, radius_km=1.5)
    
    # Filter by type if specified
    amenities = result["amenities"]
    if filter_type:
        amenities = [a for a in amenities if a["type"].lower() == filter_type.lower()]
    
    context = {
        "amenities": amenities,
        "center_lat": result["center_lat"],
        "center_lng": result["center_lon"],
        "postal_code": postal_code,
        "filter_type": filter_type,
    }
    
    return render(request, "accounts/amenities.html", context)
                    

@login_required
def amenities(request):
    if request.method == 'POST':
        print(request.POST)  
        
    return render(request, 'accounts/amenities.html')

@login_required
def properties(request):
    return render(request, 'accounts/properties.html')

@login_required
def roommates(request):
    qs = RoommateProfile.objects.select_related("user").all().order_by("-is_looking", "-id")
    form = SharingRequestForm()
    return render(request, "accounts/roommates.html", {"profiles": qs, "form": form})
        
        
            
