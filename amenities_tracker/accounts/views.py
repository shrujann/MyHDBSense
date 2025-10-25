from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth import login, authenticate, logout
from django_otp.plugins.otp_email.models import EmailDevice
from .forms import OTPForm, CustomUserCreationForm, LoginForm
from .models import CustomUser
import requests
import pandas as pd
from math import radians, sin, cos, sqrt, atan2
import concurrent.futures
import json
from django.conf import settings
from bs4 import BeautifulSoup

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
def get_onemap_token():
    url = "https://www.onemap.gov.sg/api/auth/post/getToken"
    payload = {
        "email": settings.ONEMAP_EMAIL,
        "password": settings.ONEMAP_PASSWORD
    }

    response= requests.post(url, json=payload, timeout=10)

    if response.status_code == 200:
        data = response.json()
        print("OneMap token fetched successfully.")
        print("Token:", data.get("access_token")[:10] + "...")
        return data.get("access_token")
    else:
        print("Error fetching OneMap token:", response.status_code, response.text)
        return None
# search for flats within 3km of postal code

def search_flats(request):
    postal_code = request.GET.get("q")
    flats = []
    token = get_onemap_token()

    if postal_code:
        # Step 1: Get postal code coordinates from OneMap
        try:
            url = (
                f"https://www.onemap.gov.sg/api/common/elastic/search"
                f"?searchVal={postal_code}&returnGeom=Y&getAddrDetails=Y&pageNum=1"
            )
            headers = {"Authorization": token}
            resp = requests.get(url, headers=headers, timeout=10).json()
            if resp.get("found", 0) > 0:
                lat = float(resp["results"][0]["LATITUDE"])
                lon = float(resp["results"][0]["LONGITUDE"])
            else:
                lat, lon = None, None
        except Exception as e:
            print("Error fetching postal code:", e)
            lat, lon = None, None


        # Step 2: Get town from user's postal code
        boundingbox = get_bounding_box(lat, lon, 3.0) if lat and lon else None
        postal_towns = set()
        original_town = get_hdb_town_from_postal(postal_code)
        
        fallback1 = int(postal_code[:2]) - 1
        fallback2 = int(postal_code[:2]) + 1

        original_town_sector1 = get_hdb_town_from_postal(f"{fallback1:02d}0000") if 1 <= fallback1 <= 82 else None
        original_town_sector2 = get_hdb_town_from_postal(f"{fallback2:02d}0000") if 1 <= fallback2 <= 82 else None

        postal_towns.add(original_town_sector1) if original_town_sector1 else None
        postal_towns.add(original_town_sector2) if original_town_sector2 else None
        postal_towns.add(original_town) if original_town else None

        for lat_b, lon_b in boundingbox or []:
            sector = get_sector_from_latlon(lat_b, lon_b)
            if sector:
                town = get_hdb_town_from_postal(sector)
                if town:
                    postal_towns.add(town)

        # Step 3: Fetch flats from the user's town
        if lat and lon and postal_towns:
            dataset_id = "f1765b54-a209-4718-8d38-a39237f502b3" # HDB resale flats dataset : 2024 onward
            headers = {"Authorization": token}
            months = [f"2025-{str(m).zfill(2)}" for m in range(1, 10)]  # '2025-01' to '2025-09'
            all_records = []

            try:
                with concurrent.futures.ThreadPoolExecutor() as executor: # multiple thread to speed up data fetch
                    futures = [
                    executor.submit(fetch_resale_flats_for_town, town, dataset_id, month)
                    for town in postal_towns
                    for month in months
                ]
                for future in concurrent.futures.as_completed(futures): # process each completed future
                    records = future.result()
                    all_records.extend(records)

                    for r in records:
                        block = r.get("block")
                        street = r.get("street_name")
                        if not block or not street:
                            continue
                        full_address = f"{block} {street} Singapore"
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
                                if dist <= 3.0:
                                    flats.append({
                                        "town": r.get("town"),
                                        "flat_type": r.get("flat_type"),
                                        "street_name": r.get("street_name"),
                                        "floor_area": r.get("floor_area_sqm"),
                                        "remaining_lease": r.get("remaining_lease"),
                                        "resale_price": r.get("resale_price"),
                                        "latitude": flat_lat,
                                        "longitude": flat_lon,
                                        "distance": round(dist, 2),
                                    })
                        except Exception as e:
                            print("Error geocoding flat:", e)
                            continue
            except Exception as e:
                print("Error fetching resale data for town:", postal_towns, e)

    context = {
        "flats": flats,
        "center_lat": lat if lat else 1.3521,
        "center_lng": lon if lon else 103.8198,
    }
    return render(request, "accounts/search_results.html", context)

# mapping of postal sectors to towns
POSTAL_SECTOR_TO_TOWN = {
    "01": "CENTRAL AREA",
    "02": "CENTRAL AREA",
    "03": "QUEENSTOWN",
    "04": "BUKIT MERAH",
    "05": "CLEMENTI",
    "06": "CENTRAL AREA",
    "07": "CENTRAL AREA",
    "08": "CENTRAL AREA",
    "09": "BUKIT MERAH",
    "10": "BUKIT TIMAH",
    "11": "BUKIT TIMAH",
    "12": "TOA PAYOH",
    "13": "TOA PAYOH",
    "14": "QUEENSTOWN",
    "15": "QUEENSTOWN",
    "16": "QUEENSTOWN",
    "17": "CENTRAL AREA",
    "18": "TAMPINES",
    "19": "GEYLANG",
    "20": "ANG MO KIO",
    "21": "BISHAN",
    "22": "JURONG EAST",
    "23": "BUKIT PANJANG",
    "24": "BUKIT PANJANG",
    "25": "WOODLANDS",
    "26": "BISHAN",
    "27": "YISHUN",
    "28": "SERANGOON",
    "29": "BISHAN",
    "30": "BISHAN",
    "31": "TOA PAYOH",
    "32": "TOA PAYOH",
    "33": "TOA PAYOH",
    "34": "TOA PAYOH",
    "35": "TOA PAYOH",
    "36": "TOA PAYOH",
    "37": "TOA PAYOH",
    "38": "GEYLANG",
    "39": "GEYLANG",
    "40": "GEYLANG",
    "41": "GEYLANG",
    "42": "MARINE PARADE",
    "43": "MARINE PARADE",
    "44": "MARINE PARADE",
    "45": "MARINE PARADE",
    "46": "BEDOK",
    "47": "BEDOK",
    "48": "BEDOK",
    "49": "PASIR RIS",
    "50": "PASIR RIS",
    "51": "TAMPINES",
    "52": "TAMPINES",
    "53": "SERANGOON",
    "54": "HOUGANG",
    "55": "SERANGOON",
    "56": "ANG MO KIO",
    "57": "ANG MO KIO",
    "58": "BUKIT TIMAH",
    "59": "BUKIT TIMAH",
    "60": "JURONG WEST",
    "61": "JURONG WEST",
    "62": "JURONG WEST",
    "63": "JURONG WEST",
    "64": "JURONG WEST",
    "65": "BUKIT PANJANG",
    "66": "BUKIT PANJANG",
    "67": "BUKIT PANJANG",
    "68": "CHOA CHU KANG",
    "69": "CHOA CHU KANG",
    "70": "CHOA CHU KANG",
    "71": "CHOA CHU KANG",
    "72": "WOODLANDS",
    "73": "WOODLANDS",
    "75": "YISHUN",
    "76": "SEMBAWANG",
    "77": "YISHUN",
    "78": "YISHUN",
    "79": "SENGKANG",
    "80": "SENGKANG",
    "81": "PASIR RIS",
    "82": "PUNGGOL",
}

# get town from postal code
def get_hdb_town_from_postal(postal_code):
    sector = postal_code[:2]
    return POSTAL_SECTOR_TO_TOWN.get(sector)

# get sector from lat lon
def get_sector_from_latlon(lat, lon):
    url = f"https://www.onemap.gov.sg/api/public/revgeocode?location={lat},{lon}&buffer=40&addressType=All&otherFeatures=N"
    resp = requests.get(url, timeout=10).json()
    results = resp.get("GeocodeInfo", [])
    if results:
        postal_code = results[0].get("POSTALCODE")
        if postal_code and len(postal_code) == 6:
            return postal_code[:2]
    return None

# resale flats for town
def fetch_resale_flats_for_town(town, dataset_id, months=None):
    # filters
    filters = {"town": town}
    if months:
        filters["month"] = months

    params = {
        "resource_id": dataset_id,
        "limit": 10,
        "filters": json.dumps(filters)
    }

    url = "https://data.gov.sg/api/action/datastore_search"
    print("URL:", requests.Request("GET", url, params=params).prepare().url)

    resale_data = requests.get(url, params=params, timeout=15).json()
    if resale_data.get("success"):
        records = resale_data["result"]["records"]
        print(f"Fetched {len(records)} records for town {town}, month {months}")
        return records
    return []

# get bounding box for lat lon
def get_bounding_box(lat, lon, radius_km):
    # Approximate calculation for small distances
    delta_lat = radius_km / 111  # 1 deg latitude ~ 111km
    delta_lon = radius_km / (111 * cos(radians(lat)))
    return [
        (lat + delta_lat, lon + delta_lon),  # NE
        (lat + delta_lat, lon - delta_lon),  # NW
        (lat - delta_lat, lon + delta_lon),  # SE
        (lat - delta_lat, lon - delta_lon),  # SW
    ]
# haversine formula to calculate distance between two lat/lon points
def haversine(lat1, lon1, lat2, lon2):
    R = 6371.0  # Earth radius in kilometers
    dlat = radians(lat2 - lat1)
    dlon = radians(lon2 - lon1)
    a = sin(dlat / 2)**2 + cos(radians(lat1)) * cos(radians(lat2)) * sin(dlon / 2)**2
    c = 2 * atan2(sqrt(a), sqrt(1 - a))
    distance = R * c
    return distance

# ------ Amneities Tracker Views ------
def search_amenities(request):
    postal_code = request.GET.get("q")
    amenities = []
    token = get_onemap_token()
    categories = ["schools", "eldercare", "clinic", "hawker", "mrt"]

    center_lat, center_lon = None, None

    if postal_code:
        # Step 1: Get postal code coordinates from OneMap
        try:
            url = (
                f"https://www.onemap.gov.sg/api/common/elastic/search"
                f"?searchVal={postal_code}&returnGeom=Y&getAddrDetails=Y&pageNum=1"
            )
            headers = {"Authorization": token}
            resp = requests.get(url, headers=headers, timeout=10).json()
            if resp.get("found", 0) > 0:
                lat = float(resp["results"][0]["LATITUDE"])
                lon = float(resp["results"][0]["LONGITUDE"])
            else:
                lat, lon = None, None
        except Exception as e:
            print("Error fetching postal code:", e)
            lat, lon = None, None
    
    center_lat, center_lon = lat, lon
            
       # Step 2: Fetch amenities
    if lat and lon:
        for category in categories:
            if category == "schools":
                records = findschool(postal_code)
                records_length = len(records)

                for i in range(records_length):
                    amenity_postal_code = records[i].get("postal_code")
                    try:
                        url = (
                            f"https://www.onemap.gov.sg/api/common/elastic/search"
                            f"?searchVal={amenity_postal_code}&returnGeom=Y&getAddrDetails=Y&pageNum=1"
                        )
                        headers = {"Authorization": token}
                        resp = requests.get(url, headers=headers, timeout=10).json()
                        if resp.get("found", 0) > 0:
                            amenity_lat = float(resp["results"][0]["LATITUDE"])
                            amenity_lon = float(resp["results"][0]["LONGITUDE"])
                            print(amenity_lat, amenity_lon)
                        else:
                            amenity_lat, amenity_lon = None, None
                    except Exception as e:
                        print("Error fetching postal code:", e)
                        amenity_lat, amenity_lon = None, None
                
                    if amenity_lat and amenity_lon:
                        dist = haversine(lat, lon, amenity_lat, amenity_lon)
                        if dist <= 1.5:
                            amenities.append({
                                "name": records[i].get("school_name"),
                                "type": "School",
                                "address": records[i].get("address"),
                                "postal_code": amenity_postal_code,
                                "latitude": amenity_lat,
                                "longitude": amenity_lon,
                                "distance": round(dist, 2),
                            })

            if category == "eldercare":
                records = findeldercare(postal_code)
                for record in records:
                    amenity_lat = record.get("latitude")
                    amenity_lon = record.get("longitude")
                    
                    if amenity_lat and amenity_lon:
                        dist = haversine(lat, lon, amenity_lat, amenity_lon)
                        
                        if dist <= 1.5:
                            amenities.append({
                                "name": record.get("name"),
                                "type": "Eldercare",
                                "address": record.get("address"),
                                "postal_code": record.get("postal_code"),
                                "latitude": amenity_lat,
                                "longitude": amenity_lon,
                                "distance": round(dist, 2),
                            })
            if category == "mrt":
                records = findmrt(postal_code)
                
                # Coordinates already included - no OneMap lookup needed!
                for record in records:
                    amenity_lat = record.get("latitude")
                    amenity_lon = record.get("longitude")
                    
                    if amenity_lat and amenity_lon:
                        # Calculate distance from search center
                        dist = haversine(lat, lon, amenity_lat, amenity_lon)
                        
                        # Only include if within 1.5 km radius
                        if dist <= 1.5:
                            amenities.append({
                                "name": record.get("name"),  # e.g., "JURONG EAST MRT STATION Exit A"
                                "type": "MRT Station",
                                "station_name": record.get("station_name"),
                                "exit_code": record.get("exit_code"),
                                "latitude": amenity_lat,
                                "longitude": amenity_lon,
                                "distance": round(dist, 2),
                            })

        context = {
            "amenities": amenities,
            "center_lat": center_lat if center_lat else 1.3521,
            "center_lng": center_lon if center_lon else 103.8198,
        }
    return render(request, "accounts/amenities_results.html", context)
                    


def findschool(postalcode):
    dataset_id = "d_688b934f82c1059ed0a6993d2a829089" # Schools dataset
    postal_code = str(postalcode)
    town = get_hdb_town_from_postal(postal_code)

    postal_code2_str = "50" + "0000" # hard coded - change later to search neighbouring towns
    town2 = get_hdb_town_from_postal(postal_code2_str)

    filters = {"dgp_code": [town, town2]}
    #filters = {"dgp_code": town}
    print(filters)
    params = {
        "resource_id": dataset_id,
        "limit": 1000,
        "filters": json.dumps(filters)

    }
    url = "https://data.gov.sg/api/action/datastore_search"
    print("URL:", requests.Request("GET", url, params=params).prepare().url)

    data = requests.get(url, params=params).json()
    if data.get("success"):
      records = data["result"]["records"]
      print("Fetched records:", records)
      print(f"fetched, {len(records)} records for town {town}")
      return records
    return []

def findeldercare(postalcode):
    """
    Fetch eldercare facilities from Singapore government API
    Returns list of dicts with name, address, postal_code, latitude, longitude
    """
    dataset_id = "d_f0fd1b3643ed8bd34bd403dedd7c1533"
    
    # Poll for download URL
    url = f"https://api-open.data.gov.sg/v1/public/api/datasets/{dataset_id}/poll-download"
    response = requests.get(url, timeout=10)
    json_data = response.json()
    
    # Get actual GeoJSON data
    download_url = json_data['data']['url']
    response = requests.get(download_url, timeout=10)
    geojson_data = json.loads(response.text)
    
    # Parse each feature
    eldercare_facilities = []
    for feature in geojson_data['features']:
        soup = BeautifulSoup(feature['properties']['Description'], 'html.parser')
        rows = soup.find_all('tr')
        
        # Extract data from HTML table
        data = {}
        for row in rows[1:]:
            cells = row.find_all(['th', 'td'])
            if len(cells) == 2:
                key = cells[0].get_text(strip=True)
                value = cells[1].get_text(strip=True)
                data[key] = value if value else None
        
        coords = feature['geometry']['coordinates']
        
        facility = {
            "name": data.get('NAME'),
            "address": data.get('ADDRESSSTREETNAME'),
            "postal_code": data.get('ADDRESSPOSTALCODE'),
            "latitude": coords[1],  # GeoJSON is [lon, lat]
            "longitude": coords[0],
        }
        eldercare_facilities.append(facility)
    
    return eldercare_facilities

def findmrt(postalcode):
    """
    Fetch MRT station exits from Singapore government API
    Returns list of dicts with station_name, exit_code, latitude, longitude
    """
    dataset_id = "d_b39d3a0871985372d7e1637193335da5"  # LTA MRT Station Exit (GEOJSON)
    postal_code = str(postalcode)
    
    try:
        # Step 1: Poll for download URL
        url = f"https://api-open.data.gov.sg/v1/public/api/datasets/{dataset_id}/poll-download"
        response = requests.get(url, timeout=10)
        json_data = response.json()
        
        if json_data['code'] != 0:
            print(f"API Error: {json_data.get('errMsg', 'Unknown error')}")
            return []
        
        # Step 2: Get actual data from the download URL
        download_url = json_data['data']['url']
        response = requests.get(download_url, timeout=10)
        geojson_data = json.loads(response.text)
        
        # Step 3: Parse GeoJSON features
        mrt_stations = []
        
        for feature in geojson_data['features']:
            # Parse HTML description to extract attributes
            soup = BeautifulSoup(feature['properties']['Description'], 'html.parser')
            rows = soup.find_all('tr')
            
            # Extract data from HTML table
            data = {}
            for row in rows[1:]:  # Skip header row
                cells = row.find_all(['th', 'td'])
                if len(cells) == 2:
                    key = cells[0].get_text(strip=True)
                    value = cells[1].get_text(strip=True)
                    data[key] = value if value else None
            
            # Get coordinates
            coords = feature['geometry']['coordinates']
            
            # Create station record
            station = {
                "station_name": data.get('STATION_NA'),
                "exit_code": data.get('EXIT_CODE'),
                "name": f"{data.get('STATION_NA')} {data.get('EXIT_CODE')}",  # Combined name
                "latitude": coords[1],  # GeoJSON is [lon, lat]
                "longitude": coords[0],
            }
            
            mrt_stations.append(station)
        
        return mrt_stations
        
    except Exception as e:
        print(f"Error fetching MRT data: {e}")
        return []



def home2(request):
    if request.method == 'POST':
        print(request.POST)  # Debug: see what's submitted
        
    return render(request, 'accounts/home2.html')



        
        
            
