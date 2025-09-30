from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth import login, authenticate, logout
from django_otp.plugins.otp_email.models import EmailDevice
from .forms import OTPForm, CustomUserCreationForm, LoginForm
from .models import CustomUser
import requests
import pandas as pd
from math import radians, sin, cos, sqrt, atan2

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

# search view

def haversine(lat1, lon1, lat2, lon2):
    R = 6371.0  # Earth radius in kilometers
    dlat = radians(lat2 - lat1)
    dlon = radians(lon2 - lon1)
    a = sin(dlat / 2)**2 + cos(radians(lat1)) * cos(radians(lat2)) * sin(dlon / 2)**2
    c = 2 * atan2(sqrt(a), sqrt(1 - a))
    distance = R * c
    return distance

ONEMAP_TOKEN = "eyJhbGciOiJSUzI1NiIsInR5cCI6IkpXVCJ9.eyJ1c2VyX2lkIjo5MjIwLCJmb3JldmVyIjpmYWxzZSwiaXNzIjoiT25lTWFwIiwiaWF0IjoxNzU5MjE4MDY3LCJuYmYiOjE3NTkyMTgwNjcsImV4cCI6MTc1OTQ3NzI2NywianRpIjoiOGM4ODA3MmYtZTJjMy00NDMwLWI5MjAtZDE5ZGI1NDdiNjY0In0.HERG6RZoG2AqG8r3SWuqh3TP2OzR-X36cj0SV_rjukwRYl4nTbLzcEdWEkgN3Es5Px-UuJPiHD3GmPwV2GvjzWLIEoSJtUbFql2NMWkSGIiZRfELxWdL0TJC1cKqGPVJq7l9CxrOtrqf1lucQZ6IrWqSlT6e9V33wutqENl9cO5DkmMUmgJ91bm0uAG42GVZdoH92arq8xY2oMzE_VDDsvWk9Kgj5y-PggNiLHM-dioTzLfFX1lT6LfONYwGIerGeMFIkSs6Vlz0Qu13lpHKJg8hHgkVElkKuVHaOSwwPmrAL_xBX5LnIuZWqPv0MrjBep8d-vJ_h0muV2r3h-5y7g"

def search_flats(request):
    postal_code = request.GET.get("q")  # use ?q= in URL
    flats = []

    if postal_code:
        # --- Step 1: Get postal code coordinates from OneMap ---
        try:
            url = (
                f"https://www.onemap.gov.sg/api/common/elastic/search"
                f"?searchVal={postal_code}&returnGeom=Y&getAddrDetails=Y&pageNum=1"
            )
            headers = {"Authorization": ONEMAP_TOKEN}
            resp = requests.get(url, headers=headers, timeout=10).json()

            if resp.get("found", 0) > 0:
                lat = float(resp["results"][0]["LATITUDE"])
                lon = float(resp["results"][0]["LONGITUDE"])
            else:
                lat, lon = None, None
        except Exception as e:
            print("Error fetching postal code:", e)
            lat, lon = None, None

        # --- Step 2: Fetch resale flat data ---
        if lat and lon:
            try:
                dataset_id = "8c00bf08-9124-479e-aeca-7cc411d884c4"  # official resale dataset
                resale_url = f"https://data.gov.sg/api/action/datastore_search?resource_id={dataset_id}&limit=500"
                resale_data = requests.get(resale_url, timeout=15).json()

                if resale_data.get("success"):
                    records = resale_data["result"]["records"]

                    for r in records:
                        block = r.get("block")
                        street = r.get("street_name")
                        if not block or not street:
                            continue

                        full_address = f"{block} {street} Singapore"

                        # --- Step 3: Get flat coordinates ---
                        geo_url = (
                            f"https://www.onemap.gov.sg/api/common/elastic/search"
                            f"?searchVal={full_address}&returnGeom=Y&getAddrDetails=N&pageNum=1"
                        )
                        try:
                            geo = requests.get(geo_url, headers=headers, timeout=10).json()
                            if geo.get("found", 0) > 0:
                                flat_lat = float(geo["results"][0]["LATITUDE"])
                                flat_lon = float(geo["results"][0]["LONGITUDE"])
                                dist = haversine(lat, lon, flat_lat, flat_lon)

                                if dist <= 3.0:  # within 3 km
                                    flats.append({
                                        "town": r.get("town"),
                                        "flat_type": r.get("flat_type"),
                                        "model": r.get("flat_model"),
                                        "floor_area": r.get("floor_area_sqm"),
                                        "lease_commence": r.get("lease_commence_date"),
                                        "resale_price": r.get("resale_price"),
                                        "latitude": flat_lat,
                                        "longitude": flat_lon,
                                        "distance": round(dist, 2),
                                    })
                        except Exception as e:
                            print("Error geocoding flat:", e)
                            continue
            except Exception as e:
                print("Error fetching resale data:", e)

    # --- Step 4: Pass data to template ---
    context = {
        "flats": flats,
        "center_lat": flats[0]["latitude"] if flats else 1.3521,
        "center_lng": flats[0]["longitude"] if flats else 103.8198,
    }
    return render(request, "accounts/search_results.html", context)