from django.shortcuts import render, redirect
from .forms import LocationForm
from django.http import JsonResponse
from django.views.decorators.http import require_POST
from django.views.decorators.csrf import csrf_protect
from .services import LocationController


# Initialize controller
location_controller = LocationController()


def mappage(request):
    """Render the main map page"""
    return render(request, 'mappage.html')


def map_function(request):
    """Render map page or handle map-related logic"""
    return render(request, 'mappage.html')


def form_view(request):
    """Handle location form submission and display"""
    if request.method == 'POST':
        result = location_controller.handle_location_form_submission(request.POST)
        if result['success']:
            return redirect('success')
        else:
            # Return form with errors
            return render(request, 'form.html', {'form': result['form']})
    else:
        form = LocationForm()
        return render(request, 'form.html', {'form': form})


def success(request):
    """Render success page"""
    return render(request, 'success.html')


def results_view(request):
    """Display all locations"""
    result = location_controller.get_all_locations_for_display()
    return render(request, 'results.html', {'locations': result['locations']})


@require_POST
@csrf_protect
def upvote_location(request, location_id):
    """Handle location upvote via AJAX"""
    result = location_controller.handle_upvote(location_id)
    if result['success']:
        return JsonResponse(result)
    else:
        return JsonResponse(result, status=500)


def get_coordinates(request):
    """Get coordinates for a given address"""
    address = request.GET.get('address')
    if not address:
        return JsonResponse({'error': 'Address parameter required'}, status=400)
    
    result = location_controller.handle_geocoding_request(address)
    if 'error' in result:
        return JsonResponse(result, status=404)
    return JsonResponse(result)


def get_address(request):
    """Get address details for given coordinates"""
    lat = request.GET.get('lat')
    lon = request.GET.get('lon')
    
    if not lat or not lon:
        return JsonResponse({'error': 'Latitude and longitude required'}, status=400)
    
    try:
        latitude = float(lat)
        longitude = float(lon)
        result = location_controller.handle_reverse_geocoding_request(latitude, longitude)
        if 'error' in result:
            return JsonResponse(result, status=404)
        return JsonResponse(result)
    except ValueError:
        return JsonResponse({'error': 'Invalid latitude or longitude'}, status=400)
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)