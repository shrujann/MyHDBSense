from django.shortcuts import render, redirect
from .forms import LocationForm
from .models import location
from django.http import JsonResponse
from django.shortcuts import get_object_or_404
from django.views.decorators.http import require_POST
from django.views.decorators.csrf import csrf_protect

#for reverse geocoding
import ssl
import certifi
from geopy.geocoders import Nominatim
ctx = ssl.create_default_context(cafile=certifi.where())
geolocator = Nominatim(user_agent="crowdspage", ssl_context=ctx)


# Create your views here.

def mappage(request):
    return render(request, 'mappage.html')

def map_function(request):
    # This function can be used to render a map page or handle map-related logic
    return render(request, 'mappage.html')

def form_view(request):
    if request.method == 'POST':
        form = LocationForm(request.POST)
        if form.is_valid():
            location_instance = form.save(commit=False)
            # Perform reverse geocoding to get address
            try:
                latitude = location_instance.latitude
                longitude = location_instance.longitude
                location_data = geolocator.reverse(f"{latitude}, {longitude}")
                if location_data:
                    location_instance.address = location_data.address

            except Exception as e:
                print(f"Reverse geocoding failed: {e}")
                location_instance.address = "Address not available"

            location_instance.save()
            return redirect('success')  # Redirect to a success page after submission
    else:
        form = LocationForm()

    return render(request, 'form.html', {'form': form})

def success(request):
    return render(request, 'success.html')  # render success page

def results_view(request):

    # Fetch only the required fields from the database, excluding latitude and longitude
    locations = location.objects.all()

    return render(request, 'results.html', {'locations': locations})

@require_POST
@csrf_protect
def upvote_location(request, location_id):
    
    # Get location and increment vote
    location_instance = get_object_or_404(location, id=location_id)
    location_instance.upvoteCount += 1
    location_instance.save()
    return JsonResponse({
        'upvoteCount': location_instance.upvoteCount,
        'success': True
    })

def get_coordinates(request):
    address = request.GET.get('address')
    try:
        location_data = geolocator.geocode(address)
        if location_data:
            return JsonResponse({
                'coordinates': [location_data.latitude, location_data.longitude],
                'address': location_data.address
            })
        return JsonResponse({'error': 'Address not found'}, status=404)
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)

def get_address(request):
    lat = request.GET.get('lat')
    lon = request.GET.get('lon')
    
    if not lat or not lon:
        return JsonResponse({'error': 'Latitude and longitude required'}, status=400)
    
    try:
        location_data = geolocator.reverse(f"{lat}, {lon}")
        if location_data:
            return JsonResponse({
                'address': location_data.address,
                'city': location_data.raw.get('address', {}).get('city', ''),
                'country': location_data.raw.get('address', {}).get('country', ''),
                'postcode': location_data.raw.get('address', {}).get('postcode', '')
            })
        return JsonResponse({'error': 'Address not found'}, status=404)
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)