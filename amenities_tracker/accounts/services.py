from django.conf import settings
import requests
import json
import concurrent.futures
from math import radians, sin, cos, sqrt, atan2
from bs4 import BeautifulSoup

# Constants
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

# fetch OneMap token
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
    
# get town from postal code
def get_hdb_town_from_postal(postal_code):
    sector = postal_code[:2]
    return POSTAL_SECTOR_TO_TOWN.get(sector)

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

# ==================== Core Services ====================== 

def get_coordinates_from_postal(postal_code, token):
    """
    Get latitude and longitude from postal code using OneMap API.
    Returns: (lat, lon) tuple or (None, None) if not found
    """
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
            return lat, lon
    except Exception as e:
        print(f"Error fetching postal code coordinates: {e}")
    
    return None, None

def get_nearby_towns(postal_code, lat, lon, radius_km=3.0):
    """
    Get all nearby towns within radius from postal code.
    Returns: set of town names
    """
    postal_towns = set()
    
    # Add original town
    original_town = get_hdb_town_from_postal(postal_code)
    if original_town:
        postal_towns.add(original_town)
    
    # Add adjacent sectors
    try:
        sector_num = int(postal_code[:2])
        fallback1 = sector_num - 1
        fallback2 = sector_num + 1
        
        if 1 <= fallback1 <= 82:
            town1 = get_hdb_town_from_postal(f"{fallback1:02d}0000")
            if town1:
                postal_towns.add(town1)
        
        if 1 <= fallback2 <= 82:
            town2 = get_hdb_town_from_postal(f"{fallback2:02d}0000")
            if town2:
                postal_towns.add(town2)
    except ValueError:
        pass
    
    # Add towns from bounding box
    if lat and lon:
        boundingbox = get_bounding_box(lat, lon, radius_km)
        for lat_b, lon_b in boundingbox:
            sector = get_sector_from_latlon(lat_b, lon_b)
            if sector:
                town = get_hdb_town_from_postal(f"{sector}0000")
                if town:
                    postal_towns.add(town)
    
    return postal_towns

def fetch_resale_flats_for_town(town, dataset_id, month, token):
    """
    Fetch resale flats for a specific town and month.
    Returns: list of flat records
    """
    filters = {"town": town, "month": month}
    params = {
        "resource_id": dataset_id,
        "limit": 10,
        "filters": json.dumps(filters)
    }
    
    url = "https://data.gov.sg/api/action/datastore_search"
    
    try:
        resale_data = requests.get(url, params=params, timeout=15).json()
        if resale_data.get("success"):
            records = resale_data["result"]["records"]
            print(f"Fetched {len(records)} records for town {town}, month {month}")
            return records
    except Exception as e:
        print(f"Error fetching resale flats for {town}, {month}: {e}")
    
    return []

def geocode_flat_address(block, street, token):
    """
    Get coordinates for a flat address.
    Returns: (lat, lon) tuple or (None, None)
    """
    if not block or not street:
        return None, None
    
    full_address = f"{block} {street} Singapore"
    geo_url = (
        f"https://www.onemap.gov.sg/api/common/elastic/search"
        f"?searchVal={full_address}&returnGeom=Y&getAddrDetails=N&pageNum=1"
    )
    headers = {"Authorization": token}
    
    try:
        geo = requests.get(geo_url, headers=headers, timeout=10).json()
        if geo.get("found", 0) > 0:
            flat_lat = float(geo["results"][0]["LATITUDE"])
            flat_lon = float(geo["results"][0]["LONGITUDE"])
            return flat_lat, flat_lon
    except Exception as e:
        print(f"Error geocoding flat address {full_address}: {e}")
    
    return None, None

def search_nearby_flats(postal_code, radius_km=3.0):
    """
    Main service function: Search for HDB resale flats near a postal code.
    
    Args:
        postal_code: Singapore postal code (string)
        radius_km: Search radius in kilometers (default 3.0)
    
    Returns:
        dict with:
            - flats: list of nearby flats with details
            - center_lat: search center latitude
            - center_lon: search center longitude
            - postal_towns: set of towns searched
    """
    flats = []
    token = get_onemap_token()
    
    # Step 1: Get coordinates from postal code
    lat, lon = get_coordinates_from_postal(postal_code, token)
    
    if not lat or not lon:
        return {
            "flats": [],
            "center_lat": 1.3521,  # Default Singapore center
            "center_lon": 103.8198,
            "postal_towns": set(),
            "error": "Invalid postal code"
        }
    
    # Step 2: Get nearby towns
    postal_towns = get_nearby_towns(postal_code, lat, lon, radius_km)
    
    if not postal_towns:
        return {
            "flats": [],
            "center_lat": lat,
            "center_lon": lon,
            "postal_towns": set(),
            "error": "No towns found nearby"
        }
    
    # Step 3: Fetch flats from all nearby towns (parallel requests)
    dataset_id = "f1765b54-a209-4718-8d38-a39237f502b3"
    months = [f"2025-{str(m).zfill(2)}" for m in range(1, 10)]  # 2025-01 to 2025-09
    
    try:
        with concurrent.futures.ThreadPoolExecutor() as executor:
            # Submit all fetch tasks
            futures = [
                executor.submit(fetch_resale_flats_for_town, town, dataset_id, month, token)
                for town in postal_towns
                for month in months
            ]
            
            # Process completed tasks
            for future in concurrent.futures.as_completed(futures):
                records = future.result()
                
                # Geocode and filter each flat by distance
                for record in records:
                    flat_lat, flat_lon = geocode_flat_address(
                        record.get("block"),
                        record.get("street_name"),
                        token
                    )
                    
                    if flat_lat and flat_lon:
                        dist = haversine(lat, lon, flat_lat, flat_lon)
                        
                        # Only include flats within radius
                        if dist <= radius_km:
                            flats.append({
                                "town": record.get("town"),
                                "flat_type": record.get("flat_type"),
                                "block": record.get("block"),
                                "street_name": record.get("street_name"),
                                "floor_area": record.get("floor_area_sqm"),
                                "remaining_lease": record.get("remaining_lease"),
                                "resale_price": record.get("resale_price"),
                                "latitude": flat_lat,
                                "longitude": flat_lon,
                                "distance": round(dist, 2),
                            })
    
    except Exception as e:
        print(f"Error searching flats: {e}")
    
    # Sort flats by distance
    flats.sort(key=lambda x: x["distance"])
    
    return {
        "flats": flats,
        "center_lat": lat,
        "center_lon": lon,
        "postal_towns": postal_towns,
    }

# =================== End of Services for Flat Retrival ======================

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
    
def findlibrary(postalcode):
    """
    Fetch public libraries from Singapore government API (NLB dataset)
    Returns list of dicts with name, address, postal_code, latitude, longitude
    """
    dataset_id = "d_27b8dae65d9ca1539e14d09578b17cbf"  # NLB Public Libraries
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
        libraries = []
        
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
            
            # Build full address
            address_parts = []
            if data.get('ADDRESSBLOCKHOUSENUMBER'):
                address_parts.append(data.get('ADDRESSBLOCKHOUSENUMBER'))
            if data.get('ADDRESSSTREETNAME'):
                address_parts.append(data.get('ADDRESSSTREETNAME'))
            if data.get('ADDRESSBUILDINGNAME'):
                address_parts.append(data.get('ADDRESSBUILDINGNAME'))
            
            full_address = ' '.join(address_parts) if address_parts else None
            
            # Create library record
            library = {
                "name": data.get('NAME'),
                "address": full_address,
                "postal_code": data.get('ADDRESSPOSTALCODE'),
                "building_name": data.get('ADDRESSBUILDINGNAME'),
                "floor_number": data.get('ADDRESSFLOORNUMBER'),
                "unit_number": data.get('ADDRESSUNITNUMBER'),
                "description": data.get('DESCRIPTION'),  # Library code (e.g., SRPL, OCPL)
                "hyperlink": data.get('HYPERLINK'),
                "photo_url": data.get('PHOTOURL'),
                "latitude": coords[1],  # GeoJSON is [lon, lat]
                "longitude": coords[0],
            }
            
            libraries.append(library)
        
        return libraries
        
    except Exception as e:
        print(f"Error fetching library data: {e}")
        return []
    
def findhawker(postalcode):
    """
    Fetch hawker centres from Singapore government API (NEA dataset)
    Returns list of dicts with hawker name, address, postal_code, latitude, longitude
    Safely handles missing/null fields.
    """
    dataset_id = "d_4a086da0a5553be1d89383cd90d07ecd"
    postal_code = str(postalcode)

    try:
        # Poll for download URL
        url = f"https://api-open.data.gov.sg/v1/public/api/datasets/{dataset_id}/poll-download"
        response = requests.get(url, timeout=10)
        json_data = response.json()

        if json_data['code'] != 0 or 'data' not in json_data or not json_data['data'].get('url'):
            print(f"API Error: {json_data.get('errMsg', 'Unknown error')}")
            return []

        # Fetch actual data
        download_url = json_data['data']['url']
        response = requests.get(download_url, timeout=10)
        geojson_data = json.loads(response.text)

        hawker_centres = []

        for feature in geojson_data.get('features', []):  # Default to empty list if missing
            props = feature.get('properties', {})
            coords = feature.get('geometry', {}).get('coordinates', [None, None])

            # Only take non-None address parts
            address_parts = [
                props.get('ADDRESSBLOCKHOUSENUMBER'),
                props.get('ADDRESSSTREETNAME'),
                props.get('ADDRESSBUILDINGNAME')
            ]
            full_address = ' '.join([str(part) for part in address_parts if part]) if address_parts else None

            hawker = {
                "name": props.get('NAME'),
                "description": props.get('DESCRIPTION'),
                "address": full_address,
                "postal_code": props.get('ADDRESSPOSTALCODE'),
                "building_name": props.get('ADDRESSBUILDINGNAME'),
                "street_name": props.get('ADDRESSSTREETNAME'),
                "block_house_no": props.get('ADDRESSBLOCKHOUSENUMBER'),
                "floor_number": props.get('ADDRESSFLOORNUMBER'),
                "unit_number": props.get('ADDRESSUNITNUMBER'),
                "hyperlink": props.get('HYPERLINK'),
                "photo_url": props.get('PHOTOURL'),
                "status": props.get('STATUS'),
                "awarded_date": props.get('AWARDED_DATE'),
                "implementation_date": props.get('IMPLEMENTATION_DATE'),
                "latitude": coords[1] if len(coords) > 1 else None,
                "longitude": coords[0] if coords else None,
            }

            hawker_centres.append(hawker)

        return hawker_centres

    except Exception as e:
        print(f"Error fetching hawker centre data: {e}")
        return []
    
def findtourism(postalcode):
    """
    Fetch tourism POIs from Singapore government API.
    Returns list of dicts with name, overview, image, address, lat/lon, opening hours, etc.
    Safely handles missing/null fields.
    """
    dataset_id = "d_0f2f47515425404e6c9d2a040dd87354"
    postal_code = str(postalcode)

    try:
        # Poll for download URL
        url = f"https://api-open.data.gov.sg/v1/public/api/datasets/{dataset_id}/poll-download"
        response = requests.get(url, timeout=10)
        json_data = response.json()

        if json_data['code'] != 0 or 'data' not in json_data or not json_data['data'].get('url'):
            print(f"API Error: {json_data.get('errMsg', 'Unknown error')}")
            return []

        # Fetch actual data
        download_url = json_data['data']['url']
        response = requests.get(download_url, timeout=10)
        geojson_data = json.loads(response.text)

        spots = []
        for feature in geojson_data.get('features', []):
            props = feature.get('properties', {})
            coords = feature.get('geometry', {}).get('coordinates', [None, None])

            # Parse attributes from HTML table in Description
            soup = BeautifulSoup(props.get('Description', ''), 'html.parser')
            rows = soup.find_all('tr')
            data = {}
            for row in rows[1:]:  # skip header
                cells = row.find_all(['th', 'td'])
                if len(cells) == 2:
                    key = cells[0].get_text(strip=True)
                    value = cells[1].get_text(strip=True)
                    data[key] = value if value else None

            # Get lat/lon: prefer from table, fallback to geometry
            try:
                lat = float(data.get('LATITUDE', coords[1]))
            except (TypeError, ValueError):
                lat = None
            try:
                lon = float(data.get('LONGTITUDE', coords[0]))
            except (TypeError, ValueError):
                lon = None

            spot = {
                "name": data.get("PAGETITLE"),
                "address": data.get("ADDRESS"),
                "postal_code": data.get("POSTALCODE"),
                "latitude": lat,
                "longitude": lon,
                "overview": data.get("OVERVIEW"),
                "external_link": data.get("EXTERNAL_LINK"),
                "meta_description": data.get("META_DESCRIPTION"),
                "opening_hours": data.get("OPENING_HOURS"),
                "image_url": data.get("IMAGE_PATH"),
                "image_alt": data.get("IMAGE_ALT_TEXT"),
                "photocredits": data.get("PHOTOCREDITS"),
                "url_path": data.get("URL_PATH"),
                "lastmodified": data.get("LASTMODIFIED"),
            }

            spots.append(spot)

        return spots

    except Exception as e:
        print(f"Error fetching tourism POI data: {e}")
        return []

def findpreschool(postalcode):
    """
    Fetch pre-school locations from Singapore government API.
    Returns list of dicts with name, code, lat/lon, and updated date.
    """
    dataset_id = "d_61eefab99958fd70e6aab17320a71f1c"
    postal_code = str(postalcode)

    try:
        # Poll for download URL
        url = f"https://api-open.data.gov.sg/v1/public/api/datasets/{dataset_id}/poll-download"
        response = requests.get(url, timeout=10)
        json_data = response.json()

        if json_data['code'] != 0 or 'data' not in json_data or not json_data['data'].get('url'):
            print(f"API Error: {json_data.get('errMsg', 'Unknown error')}")
            return []

        # Fetch actual data
        download_url = json_data['data']['url']
        response = requests.get(download_url, timeout=10)
        geojson_data = json.loads(response.text)

        preschools = []
        for feature in geojson_data.get('features', []):
            props = feature.get('properties', {})
            coords = feature.get('geometry', {}).get('coordinates', [None, None])

            # Parse from HTML table in Description
            soup = BeautifulSoup(props.get('Description', ''), 'html.parser')
            rows = soup.find_all('tr')
            data = {}
            for row in rows[1:]:  # skip header
                cells = row.find_all(['th', 'td'])
                if len(cells) == 2:
                    key = cells[0].get_text(strip=True)
                    value = cells[1].get_text(strip=True)
                    data[key] = value if value else None

            preschool = {
                "name": data.get("CENTRE_NAME"),
                "code": data.get("CENTRE_CODE"),
                "latitude": coords[1] if len(coords) > 1 else None,
                "longitude": coords[0] if coords else None,
                "last_update": data.get("FMEL_UPD_D"),
            }

            preschools.append(preschool)

        return preschools

    except Exception as e:
        print(f"Error fetching preschool location data: {e}")
        return []
    
def findchildcare(postalcode):
    """
    Fetch childcare services from Singapore government API.
    Returns list of dicts with name, address, postal_code, lat/lon.
    Safely handles missing/null fields.
    """
    dataset_id = "d_5d668e3f544335f8028f546827b773b4"
    postal_code = str(postalcode)

    try:
        # Poll for download URL
        url = f"https://api-open.data.gov.sg/v1/public/api/datasets/{dataset_id}/poll-download"
        response = requests.get(url, timeout=10)
        json_data = response.json()

        if json_data['code'] != 0 or 'data' not in json_data or not json_data['data'].get('url'):
            print(f"API Error: {json_data.get('errMsg', 'Unknown error')}")
            return []

        # Fetch actual GeoJSON data
        download_url = json_data['data']['url']
        response = requests.get(download_url, timeout=10)
        geojson_data = json.loads(response.text)

        childcare = []
        for feature in geojson_data.get('features', []):
            props = feature.get('properties', {})
            coords = feature.get('geometry', {}).get('coordinates', [None, None])

            # Parse attributes from HTML table in Description
            soup = BeautifulSoup(props.get('Description', ''), 'html.parser')
            rows = soup.find_all('tr')
            data = {}
            for row in rows[1:]:  # skip header
                cells = row.find_all(['th', 'td'])
                if len(cells) == 2:
                    key = cells[0].get_text(strip=True)
                    value = cells[1].get_text(strip=True)
                    data[key] = value if value else None

            # Safely build address using only non-empty fields
            address_parts = [
                data.get('ADDRESSBLOCKHOUSENUMBER'),
                data.get('ADDRESSSTREETNAME'),
                data.get('ADDRESSBUILDINGNAME')
            ]
            address = ' '.join([str(p) for p in address_parts if p]) if any(address_parts) else None

            entry = {
                "name": data.get("NAME"),
                "address": address or data.get("ADDRESSSTREETNAME"),
                "postal_code": data.get("ADDRESSPOSTALCODE"),
                "latitude": coords[1] if len(coords) > 1 else None,
                "longitude": coords[0] if coords else None,
                "last_update": data.get("FMEL_UPD_D"),
                "description": data.get("DESCRIPTION"),
            }

            childcare.append(entry)

        return childcare

    except Exception as e:
        print(f"Error fetching childcare data: {e}")
        return []

def findgym(postalcode):
    """
    Fetch gyms@sg locations from Singapore government API.
    Returns list of dicts with gym name, address, opening hours, postal_code, and lat/lon.
    Safely handles missing/null fields.
    """
    dataset_id = "d_b3ae090692ecf632116c9885cfbd3424"
    postal_code = str(postalcode)

    try:
        # Poll for download URL
        url = f"https://api-open.data.gov.sg/v1/public/api/datasets/{dataset_id}/poll-download"
        response = requests.get(url, timeout=10)
        json_data = response.json()

        if json_data['code'] != 0 or 'data' not in json_data or not json_data['data'].get('url'):
            print(f"API Error: {json_data.get('errMsg', 'Unknown error')}")
            return []

        # Fetch actual GeoJSON data
        download_url = json_data['data']['url']
        response = requests.get(download_url, timeout=10)
        geojson_data = json.loads(response.text)

        gyms = []
        for feature in geojson_data.get('features', []):
            props = feature.get('properties', {})
            coords = feature.get('geometry', {}).get('coordinates', [None, None])

            # Parse attributes from HTML table in Description
            soup = BeautifulSoup(props.get('Description', ''), 'html.parser')
            rows = soup.find_all('tr')
            data = {}
            for row in rows[1:]:  # skip header
                cells = row.find_all(['th', 'td'])
                if len(cells) == 2:
                    key = cells[0].get_text(strip=True)
                    value = cells[1].get_text(strip=True)
                    data[key] = value if value else None

            # Build address from available components
            address_parts = [
                data.get('ADDRESSBLOCKHOUSENUMBER'),
                data.get('ADDRESSSTREETNAME'),
                data.get('ADDRESSBUILDINGNAME')
            ]
            address = ' '.join([str(p) for p in address_parts if p]) if any(address_parts) else None

            record = {
                "name": data.get("NAME"),
                "description": data.get("DESCRIPTION"),
                "address": address or data.get("ADDRESSSTREETNAME"),
                "postal_code": data.get("ADDRESSPOSTALCODE"),
                "building_name": data.get("ADDRESSBUILDINGNAME"),
                "latitude": coords[1] if len(coords) > 1 else None,
                "longitude": coords[0] if coords else None,
                "last_update": data.get("FMEL_UPD_D"),
                "photo_url": data.get("PHOTOURL"),
                "hyperlink": data.get("HYPERLINK"),
                "floor_number": data.get("ADDRESSFLOORNUMBER"),
                "unit_number": data.get("ADDRESSUNITNUMBER"),
            }

            gyms.append(record)

        return gyms

    except Exception as e:
        print(f"Error fetching gym data: {e}")
        return []
    
def findsportsg(postalcode):
    """
    Fetch SportSG/ActiveSG facilities from Singapore government API.
    Handles Point and Polygon geometries; Polygon returns the centroid.
    Returns list of dicts with centre name, address, contacts, facility info, and coordinates.
    """
    dataset_id = "d_9b87bab59d036a60fad2a91530e10773"
    postal_code = str(postalcode)

    try:
        url = f"https://api-open.data.gov.sg/v1/public/api/datasets/{dataset_id}/poll-download"
        response = requests.get(url, timeout=10)
        json_data = response.json()

        if json_data['code'] != 0 or 'data' not in json_data or not json_data['data'].get('url'):
            print(f"API Error: {json_data.get('errMsg', 'Unknown error')}")
            return []

        download_url = json_data['data']['url']
        response = requests.get(download_url, timeout=10)
        geojson_data = json.loads(response.text)

        facilities = []
        for feature in geojson_data.get('features', []):
            props = feature.get('properties', {})
            geom = feature.get('geometry', {})
            coords = None

            # Geometry: support both Point and Polygon (use centroid)
            if geom.get('type') == 'Point':
                coords = geom.get('coordinates', [None, None])
                lat, lon = coords[1], coords[0]
            elif geom.get('type') == 'Polygon':
                poly = geom.get('coordinates', [])
                # Get centroid if possible (average of all points, 2D only)
                if poly and isinstance(poly, list) and poly[0]:
                    xs = [pt[0] for pt in poly[0] if len(pt) >= 2]
                    ys = [pt[1] for pt in poly[0] if len(pt) >= 2]
                    if xs and ys:
                        lon = sum(xs) / len(xs)
                        lat = sum(ys) / len(ys)
                    else:
                        lat, lon = None, None
                else:
                    lat, lon = None, None
            else:
                lat, lon = None, None

            # Parse values from HTML Description table
            soup = BeautifulSoup(props.get('Description', ''), 'html.parser')
            rows = soup.find_all('tr')
            data = {}
            for row in rows[1:]:
                cells = row.find_all(['th', 'td'])
                if len(cells) == 2:
                    key = cells[0].get_text(strip=True)
                    value = cells[1].get_text(strip=True)
                    data[key] = value if value else None

            record = {
                "name": data.get("SPORTS_CEN"),
                "facility_type": data.get("FACILITIES"),
                "address": f"{data.get('HOUSE_BLOC', '')} {data.get('ROAD_NAME', '')}".strip() if data.get('HOUSE_BLOC') or data.get('ROAD_NAME') else None,
                "postal_code": data.get("POSTAL_COD"),
                "contacts": data.get("CONTACT_NO"),
                "operating_hours": data.get("STADIUM_OP") or data.get("GYM_OPERAT") or data.get("SWIMMING_C") or data.get("SPORTS_HAL"),
                "booking_url": data.get("BOOKING_LI"),
                "info_url": data.get("INFORMATIO"),
                "status": data.get("STATUS"),
                "latitude": lat,
                "longitude": lon,
                "last_update": data.get("FMEL_UPD_D"),
                # Include any facility counts etc as needed, e.g. Badminton: data.get("BADMINTON_") etc.
                "description": data.get("FACILITY_I"),
            }

            facilities.append(record)

        return facilities

    except Exception as e:
        print(f"Error fetching sportsG data: {e}")
        return []
    
def findpark(postalcode):
    """
    Fetch national parks/nature reserves from Singapore government API.
    Returns list of dicts with park name, id, lat/lon.
    """
    dataset_id = "d_0542d48f0991541706b58059381a6eca"
    postal_code = str(postalcode)

    try:
        # Poll for download URL
        url = f"https://api-open.data.gov.sg/v1/public/api/datasets/{dataset_id}/poll-download"
        response = requests.get(url, timeout=10)
        json_data = response.json()

        if json_data['code'] != 0 or 'data' not in json_data or not json_data['data'].get('url'):
            print(f"API Error: {json_data.get('errMsg', 'Unknown error')}")
            return []

        download_url = json_data['data']['url']
        response = requests.get(download_url, timeout=10)
        geojson_data = json.loads(response.text)

        parks = []
        for feature in geojson_data.get('features', []):
            props = feature.get('properties', {})
            coords = feature.get('geometry', {}).get('coordinates', [None, None])
            
            park = {
                "name": props.get("NAME"),
                "latitude": coords[1] if len(coords) > 1 else None,
                "longitude": coords[0] if coords else None,
                "id": props.get("OBJECTID"),
            }

            parks.append(park)

        return parks

    except Exception as e:
        print(f"Error fetching park data: {e}")
        return []
    
def findmarketcentre(postalcode):
    """
    Fetch market centres from Singapore government API.
    Returns list of dicts with centre name, address, postal_code, coordinates, stall counts, etc.
    """
    dataset_id = "d_a57a245b3cf3ec76ad36d55393a16e97"
    postal_code = str(postalcode)

    try:
        # Poll for download URL
        url = f"https://api-open.data.gov.sg/v1/public/api/datasets/{dataset_id}/poll-download"
        response = requests.get(url, timeout=10)
        json_data = response.json()

        if json_data['code'] != 0 or 'data' not in json_data or not json_data['data'].get('url'):
            print(f"API Error: {json_data.get('errMsg', 'Unknown error')}")
            return []

        download_url = json_data['data']['url']
        response = requests.get(download_url, timeout=10)
        geojson_data = json.loads(response.text)

        centres = []
        for feature in geojson_data.get('features', []):
            props = feature.get('properties', {})
            coords = feature.get('geometry', {}).get('coordinates', [None, None])

            # Parse data from Description HTML
            soup = BeautifulSoup(props.get('Description', ''), 'html.parser')
            rows = soup.find_all('tr')
            data = {}
            for row in rows[1:]:
                cells = row.find_all(['th', 'td'])
                if len(cells) == 2:
                    key = cells[0].get_text(strip=True)
                    value = cells[1].get_text(strip=True)
                    data[key] = value if value else None

            record = {
                "name": data.get("NAME_OF_CENTRE"),
                "location_centre": data.get("LOCATION_CENTRE"),
                "total_stalls": data.get("TOTAL_STALLS"),
                "market_stalls": data.get("MP_STALLS"),
                "cf_stalls": data.get("CF_STALLS"),
                "type": data.get("TYPE"),
                "owner": data.get("OWNER"),
                "postal_code": data.get("POSTAL_CODE"),
                "latitude": coords[1] if len(coords) > 1 else None,
                "longitude": coords[0] if coords else None,
            }

            centres.append(record)

        return centres

    except Exception as e:
        print(f"Error fetching market centre data: {e}")
        return []
    
def findsupermarket(postalcode):
    """
    Fetch supermarkets from Singapore government API.
    Returns list of dicts with name, address, postal_code, coordinates, and license info.
    """
    dataset_id = "d_cac2c32f01960a3ad7202a99c27268a0"
    postal_code = str(postalcode)

    try:
        # Poll for download URL
        url = f"https://api-open.data.gov.sg/v1/public/api/datasets/{dataset_id}/poll-download"
        response = requests.get(url, timeout=10)
        json_data = response.json()

        if json_data['code'] != 0 or 'data' not in json_data or not json_data['data'].get('url'):
            print(f"API Error: {json_data.get('errMsg', 'Unknown error')}")
            return []

        download_url = json_data['data']['url']
        response = requests.get(download_url, timeout=10)
        geojson_data = json.loads(response.text)

        markets = []
        for feature in geojson_data.get('features', []):
            props = feature.get('properties', {})
            coords = feature.get('geometry', {}).get('coordinates', [None, None])

            # Parse data from Description HTML
            soup = BeautifulSoup(props.get('Description', ''), 'html.parser')
            rows = soup.find_all('tr')
            data = {}
            for row in rows[1:]:
                cells = row.find_all(['th', 'td'])
                if len(cells) == 2:
                    key = cells[0].get_text(strip=True)
                    value = cells[1].get_text(strip=True)
                    data[key] = value if value else None

            # Build address from parts
            address_parts = [data.get("BLK_HOUSE"), data.get("STR_NAME"), data.get("UNIT_NO")]
            address = ' '.join(str(x) for x in address_parts if x) if any(address_parts) else None

            record = {
                "name": data.get("LIC_NAME"),
                "address": address,
                "postal_code": data.get("POSTCODE"),
                "latitude": coords[1] if len(coords) > 1 else None,
                "longitude": coords[0] if coords else None,
                "license_no": data.get("LIC_NO"),
                "last_update": data.get("FMEL_UPD_D"),
            }

            markets.append(record)

        return markets

    except Exception as e:
        print(f"Error fetching supermarket data: {e}")
        return []

def findchas(postalcode):
    """
    Fetch CHAS clinics from Singapore government API (MOH dataset - GeoJSON version)
    Returns list of dicts with clinic name, address, postal_code, latitude, longitude
    """
    dataset_id = "d_548c33ea2d99e29ec63a7cc9edcccedc"  # MOH CHAS Clinics (GEOJSON)
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
        clinics = []
        
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
            
            # Build full address
            address_parts = []
            if data.get('BLK_HSE_NO'):
                address_parts.append(data.get('BLK_HSE_NO'))
            if data.get('STREET_NAME'):
                address_parts.append(data.get('STREET_NAME'))
            if data.get('BUILDING_NAME'):
                address_parts.append(data.get('BUILDING_NAME'))
            
            full_address = ' '.join(address_parts) if address_parts else None
            
            # Create clinic record
            clinic = {
                "name": data.get('HCI_NAME'),
                "hci_code": data.get('HCI_CODE'),
                "licence_type": data.get('LICENCE_TYPE'),
                "phone": data.get('HCI_TEL'),
                "address": full_address,
                "postal_code": data.get('POSTAL_CD'),
                "building_name": data.get('BUILDING_NAME'),
                "floor_number": data.get('FLOOR_NO'),
                "unit_number": data.get('UNIT_NO'),
                "street_name": data.get('STREET_NAME'),
                "block_house_no": data.get('BLK_HSE_NO'),
                "programme_code": data.get('CLINIC_PROGRAMME_CODE'),
                "latitude": coords[1],  # GeoJSON is [lon, lat]
                "longitude": coords[0],
            }
            
            clinics.append(clinic)
        
        return clinics
        
    except Exception as e:
        print(f"Error fetching CHAS clinic data: {e}")
        return []
    
    #============================== Search Amenities Views ==============================#

    # =================== Search Amenities Service ======================

def search_nearby_amenities(postal_code, radius_km=1.5):
    """
    Search for all amenities near a postal code.
    
    Args:
        postal_code: Singapore postal code (string)
        radius_km: Search radius in kilometers (default 1.5)
    
    Returns:
        dict with:
            - amenities: list of all nearby amenities
            - center_lat: search center latitude
            - center_lon: search center longitude
            - error: error message if any
    """
    amenities = []
    token = get_onemap_token()
    
    # Step 1: Get coordinates from postal code
    lat, lon = get_coordinates_from_postal(postal_code, token)
    
    if not lat or not lon:
        return {
            "amenities": [],
            "center_lat": 1.3521,  # Default Singapore center
            "center_lon": 103.8198,
            "error": "Invalid postal code"
        }
    
    # Step 2: Define category mapping and processing functions
    category_processors = {
        "schools": lambda: _process_schools(postal_code, lat, lon, radius_km, token),
        "eldercare": lambda: _process_standard_amenity(findeldercare(postal_code), "Eldercare", lat, lon, radius_km),
        "mrt": lambda: _process_standard_amenity(findmrt(postal_code), "MRT Station", lat, lon, radius_km),
        "library": lambda: _process_standard_amenity(findlibrary(postal_code), "Library", lat, lon, radius_km),
        "clinic": lambda: _process_chas_clinics(findchas(postal_code), lat, lon, radius_km),
        "hawker": lambda: _process_standard_amenity(findhawker(postal_code), "Hawker Centre", lat, lon, radius_km),
        "tourism": lambda: _process_tourism(findtourism(postal_code), lat, lon, radius_km),
        "preschool": lambda: _process_preschool(findpreschool(postal_code), lat, lon, radius_km),
        "childcare": lambda: _process_childcare(findchildcare(postal_code), lat, lon, radius_km),
        "gym": lambda: _process_gym(findgym(postal_code), lat, lon, radius_km),
        "sportsg": lambda: _process_sportsg(findsportsg(postal_code), lat, lon, radius_km),
        "parks": lambda: _process_parks(findpark(postal_code), lat, lon, radius_km),
        "marketcentre": lambda: _process_market_centre(findmarketcentre(postal_code), lat, lon, radius_km),
        "supermarket": lambda: _process_supermarket(findsupermarket(postal_code), lat, lon, radius_km),
    }
    
    # Step 3: Process all categories
    for category, processor in category_processors.items():
        try:
            category_amenities = processor()
            amenities.extend(category_amenities)
        except Exception as e:
            print(f"Error processing {category}: {e}")
    
    # Step 4: Sort by distance
    amenities.sort(key=lambda x: x.get("distance", 999))
    
    return {
        "amenities": amenities,
        "center_lat": lat,
        "center_lon": lon,
    }


# ============ PRIVATE HELPER FUNCTIONS FOR AMENITY PROCESSING ============

def _process_schools(postal_code, lat, lon, radius_km, token):
    """Process schools (requires geocoding via postal code)"""
    amenities = []
    records = findschool(postal_code)
    
    for record in records:
        amenity_postal_code = record.get("postal_code")
        if not amenity_postal_code:
            continue
        
        # Get coordinates from postal code
        amenity_lat, amenity_lon = get_coordinates_from_postal(amenity_postal_code, token)
        
        if amenity_lat and amenity_lon:
            dist = haversine(lat, lon, amenity_lat, amenity_lon)
            if dist <= radius_km:
                amenities.append({
                    "name": record.get("school_name"),
                    "type": "School",
                    "address": record.get("address"),
                    "postal_code": amenity_postal_code,
                    "latitude": amenity_lat,
                    "longitude": amenity_lon,
                    "distance": round(dist, 2),
                })
    
    return amenities


def _process_standard_amenity(records, amenity_type, lat, lon, radius_km):
    """Process amenities that already have coordinates"""
    amenities = []
    
    for record in records:
        amenity_lat = record.get("latitude")
        amenity_lon = record.get("longitude")
        
        if amenity_lat and amenity_lon:
            dist = haversine(lat, lon, amenity_lat, amenity_lon)
            
            if dist <= radius_km:
                amenity = {
                    "name": record.get("name"),
                    "type": amenity_type,
                    "latitude": amenity_lat,
                    "longitude": amenity_lon,
                    "distance": round(dist, 2),
                }
                
                # Add optional fields if they exist
                if record.get("address"):
                    amenity["address"] = record.get("address")
                if record.get("postal_code"):
                    amenity["postal_code"] = record.get("postal_code")
                if record.get("building_name"):
                    amenity["building_name"] = record.get("building_name")
                if record.get("description"):
                    amenity["description"] = record.get("description")
                
                # MRT-specific fields
                if amenity_type == "MRT Station":
                    amenity["station_name"] = record.get("station_name")
                    amenity["exit_code"] = record.get("exit_code")
                
                amenities.append(amenity)
    
    return amenities


def _process_chas_clinics(records, lat, lon, radius_km):
    """Process CHAS clinics with phone numbers"""
    amenities = []
    
    for record in records:
        amenity_lat = record.get("latitude")
        amenity_lon = record.get("longitude")
        
        if amenity_lat and amenity_lon:
            dist = haversine(lat, lon, amenity_lat, amenity_lon)
            
            if dist <= radius_km:
                amenities.append({
                    "name": record.get("name"),
                    "type": "CHAS Clinic",
                    "address": record.get("address"),
                    "postal_code": record.get("postal_code"),
                    "phone": record.get("phone"),
                    "building_name": record.get("building_name"),
                    "latitude": amenity_lat,
                    "longitude": amenity_lon,
                    "distance": round(dist, 2),
                })
    
    return amenities


def _process_tourism(records, lat, lon, radius_km):
    """Process tourism POIs with extended info"""
    amenities = []
    
    for record in records:
        amenity_lat = record.get("latitude")
        amenity_lon = record.get("longitude")
        
        if amenity_lat and amenity_lon:
            dist = haversine(lat, lon, amenity_lat, amenity_lon)
            
            if dist <= radius_km:
                amenities.append({
                    "name": record.get("name"),
                    "type": "Tourism",
                    "address": record.get("address"),
                    "postal_code": record.get("postal_code"),
                    "latitude": amenity_lat,
                    "longitude": amenity_lon,
                    "overview": record.get("overview"),
                    "external_link": record.get("external_link"),
                    "image_url": record.get("image_url"),
                    "opening_hours": record.get("opening_hours"),
                    "distance": round(dist, 2),
                })
    
    return amenities


def _process_preschool(records, lat, lon, radius_km):
    """Process preschools"""
    amenities = []
    
    for record in records:
        amenity_lat = record.get("latitude")
        amenity_lon = record.get("longitude")
        
        if amenity_lat and amenity_lon:
            dist = haversine(lat, lon, amenity_lat, amenity_lon)
            
            if dist <= radius_km:
                amenities.append({
                    "name": record.get("name"),
                    "type": "Preschool",
                    "code": record.get("code"),
                    "latitude": amenity_lat,
                    "longitude": amenity_lon,
                    "last_update": record.get("last_update"),
                    "distance": round(dist, 2),
                })
    
    return amenities


def _process_childcare(records, lat, lon, radius_km):
    """Process childcare facilities"""
    amenities = []
    
    for record in records:
        amenity_lat = record.get("latitude")
        amenity_lon = record.get("longitude")
        
        if amenity_lat and amenity_lon:
            dist = haversine(lat, lon, amenity_lat, amenity_lon)
            
            if dist <= radius_km:
                amenities.append({
                    "name": record.get("name"),
                    "type": "Childcare",
                    "address": record.get("address"),
                    "postal_code": record.get("postal_code"),
                    "latitude": amenity_lat,
                    "longitude": amenity_lon,
                    "last_update": record.get("last_update"),
                    "description": record.get("description"),
                    "distance": round(dist, 2),
                })
    
    return amenities


def _process_gym(records, lat, lon, radius_km):
    """Process gyms"""
    amenities = []
    
    for record in records:
        amenity_lat = record.get("latitude")
        amenity_lon = record.get("longitude")
        
        if amenity_lat and amenity_lon:
            dist = haversine(lat, lon, amenity_lat, amenity_lon)
            
            if dist <= radius_km:
                amenities.append({
                    "name": record.get("name"),
                    "type": "Gym",
                    "address": record.get("address"),
                    "postal_code": record.get("postal_code"),
                    "latitude": amenity_lat,
                    "longitude": amenity_lon,
                    "last_update": record.get("last_update"),
                    "description": record.get("description"),
                    "distance": round(dist, 2),
                })
    
    return amenities


def _process_sportsg(records, lat, lon, radius_km):
    """Process SportSG facilities"""
    amenities = []
    
    for record in records:
        amenity_lat = record.get("latitude")
        amenity_lon = record.get("longitude")
        
        if amenity_lat and amenity_lon:
            dist = haversine(lat, lon, amenity_lat, amenity_lon)
            
            if dist <= radius_km:
                amenities.append({
                    "name": record.get("name"),
                    "type": "SportSG",
                    "address": record.get("address"),
                    "postal_code": record.get("postal_code"),
                    "contacts": record.get("contacts"),
                    "operating_hours": record.get("operating_hours"),
                    "info_url": record.get("info_url"),
                    "status": record.get("status"),
                    "latitude": amenity_lat,
                    "longitude": amenity_lon,
                    "distance": round(dist, 2),
                    "facility_type": record.get("facility_type"),
                })
    
    return amenities


def _process_parks(records, lat, lon, radius_km):
    """Process parks"""
    amenities = []
    
    for record in records:
        amenity_lat = record.get("latitude")
        amenity_lon = record.get("longitude")
        
        if amenity_lat and amenity_lon:
            dist = haversine(lat, lon, amenity_lat, amenity_lon)
            
            if dist <= radius_km:
                amenities.append({
                    "name": record.get("name"),
                    "type": "Park",
                    "park_id": record.get("id"),
                    "latitude": amenity_lat,
                    "longitude": amenity_lon,
                    "distance": round(dist, 2),
                })
    
    return amenities


def _process_market_centre(records, lat, lon, radius_km):
    """Process market centres"""
    amenities = []
    
    for record in records:
        amenity_lat = record.get("latitude")
        amenity_lon = record.get("longitude")
        
        if amenity_lat and amenity_lon:
            dist = haversine(lat, lon, amenity_lat, amenity_lon)
            
            if dist <= radius_km:
                amenities.append({
                    "name": record.get("name"),
                    "type": "Market Centre",
                    "address": record.get("location_centre"),
                    "postal_code": record.get("postal_code"),
                    "latitude": amenity_lat,
                    "longitude": amenity_lon,
                    "total_stalls": record.get("total_stalls"),
                    "market_stalls": record.get("market_stalls"),
                    "cf_stalls": record.get("cf_stalls"),
                    "centre_type": record.get("type"),
                    "owner": record.get("owner"),
                    "distance": round(dist, 2),
                })
    
    return amenities


def _process_supermarket(records, lat, lon, radius_km):
    """Process supermarkets"""
    amenities = []
    
    for record in records:
        amenity_lat = record.get("latitude")
        amenity_lon = record.get("longitude")
        
        if amenity_lat and amenity_lon:
            dist = haversine(lat, lon, amenity_lat, amenity_lon)
            
            if dist <= radius_km:
                amenities.append({
                    "name": record.get("name"),
                    "type": "Supermarket",
                    "address": record.get("address"),
                    "postal_code": record.get("postal_code"),
                    "latitude": amenity_lat,
                    "longitude": amenity_lon,
                    "license_no": record.get("license_no"),
                    "last_update": record.get("last_update"),
                    "distance": round(dist, 2),
                })
    
    return amenities
# =================== End of Amenities Tracker Views ======================
