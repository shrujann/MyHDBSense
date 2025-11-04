from django.db.models import Q
from .models import RoommateProfile, ContactAttempt, CustomUser
from django.contrib.auth import get_user_model
from django.core.mail import send_mail
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth import login, authenticate, logout
from django_otp.plugins.otp_email.models import EmailDevice
from .forms import RoommateProfileForm, SharingRequestForm, ContactMessageForm, OTPForm, CustomUserCreationForm, LoginForm
from .models import CustomUser
from . import services

# registeration view
def register(request):
    if request.method == "POST":
        form = CustomUserCreationForm(request.POST)
        if form.is_valid():
            user = form.save(commit=False)
            user.is_active = False  # prevent login until OTP verified
            user.save()

            # create OTP email device
            device = EmailDevice.objects.create(
                user=user,
                name="default",
                confirmed=False
            )
            device.generate_challenge()  # this sends the OTP to the user’s email

            return redirect("verify_otp", user_id=user.id)
    else:
        form = CustomUserCreationForm()
    return render(request, "accounts/register.html", {"form": form})

# view to setup 2FA via email

def send_otp(user):
    device, created = EmailDevice.objects.get_or_create(user=user, name='default')
    device.generate_challenge()

# verify OTP view

def verify_otp(request, user_id):
    user = get_object_or_404(CustomUser, id=user_id)  # get the user object or 404 if not found
    device = EmailDevice.objects.filter(user=user, name="default").first()  # get the email device for the user

    if request.method == "POST":
        form = OTPForm(request.POST)  # bind data to form
        if form.is_valid():  # if the form is valid
            otp = form.cleaned_data["otp"]  # get the OTP from the form
            if device and device.verify_token(otp):  # verify the OTP
                user.is_active = True  # activate the user
                user.save()  # save the user to database
                login(request, user)  # auto login after successful OTP verification
                return redirect("home")  # Redirect to a success page.
            else:
                form.add_error("otp", "Invalid OTP. Please try again.")  # show error on the form
    else:
        form = OTPForm()

    return render(request, "accounts/verify_otp.html", {"form": form})  # render the OTP verification form


# Log in view
def login_view(request):
    if request.method == "POST":
        form = LoginForm(request.POST)
        if form.is_valid():
            username = form.cleaned_data["username"]
            password = form.cleaned_data["password"]
            user = authenticate(request, username=username, password=password)

            if user is not None:
                login(request, user)
                return redirect("home")  # Redirect to a success page.
            else:
                form.add_error(None, "Invalid username or password.")
    else:
        form = LoginForm()
    return render(request, "accounts/login.html", {"form": form})

# Logout view
def logout_view(request):
    logout(request)
    return redirect("login")  # Redirect to login page after logout

# home view
def home(request):
    return render(request, "accounts/home.html")  # render the home page

# Retrieve ONEMAP Token

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
    
    return render(request, "accounts/amenities_results.html", context)
                    

#  home2 view for testing
def home2(request):
    if request.method == 'POST':
        print(request.POST)  # Debug: see what's submitted
        
    return render(request, 'accounts/home2.html')



        
        
            
