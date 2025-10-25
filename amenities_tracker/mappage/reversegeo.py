
#Ignore this file, just for testing reverse geocoding cuz macbook is fking stupid

import ssl
import certifi
from geopy.geocoders import Nominatim

# Initialize the geolocator
geolocator = Nominatim(user_agent="your_app_name")

# Perform reverse geocoding
latitude = 1.3548506884992064
longitude = 103.68663024226748
location = geolocator.reverse(f"{latitude}, {longitude}")

# Get the full address
print(location.address)
