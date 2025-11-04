import ssl
import certifi
from geopy.geocoders import Nominatim
from django.shortcuts import get_object_or_404
from .models import location
from typing import List, Optional, Dict, Any, Tuple


class GeocodingService:
    """Service for handling geocoding and reverse geocoding operations"""
    
    def __init__(self):
        ctx = ssl.create_default_context(cafile=certifi.where())
        self.geolocator = Nominatim(user_agent="crowdspage", ssl_context=ctx)
    
    def get_address_from_coordinates(self, latitude: float, longitude: float) -> Optional[str]:
        """
        Get address from latitude and longitude coordinates
        
        Args:
            latitude (float): Latitude coordinate
            longitude (float): Longitude coordinate
            
        Returns:
            Optional[str]: Address string or None if not found
        """
        try:
            location_data = self.geolocator.reverse(f"{latitude}, {longitude}")
            return location_data.address if location_data else None
        except Exception as e:
            print(f"Reverse geocoding failed: {e}")
            return None
    
    def get_coordinates_from_address(self, address: str) -> Optional[Tuple[float, float]]:
        """
        Get coordinates from address string
        
        Args:
            address (str): Address to geocode
            
        Returns:
            Optional[Tuple[float, float]]: (latitude, longitude) or None if not found
        """
        try:
            location_data = self.geolocator.geocode(address)
            if location_data:
                return (location_data.latitude, location_data.longitude)
            return None
        except Exception as e:
            print(f"Geocoding failed: {e}")
            return None
    
    def get_detailed_address_info(self, latitude: float, longitude: float) -> Optional[Dict[str, Any]]:
        """
        Get detailed address information from coordinates
        
        Args:
            latitude (float): Latitude coordinate
            longitude (float): Longitude coordinate
            
        Returns:
            Optional[Dict[str, Any]]: Dictionary with address details or None if not found
        """
        try:
            location_data = self.geolocator.reverse(f"{latitude}, {longitude}")
            if location_data:
                address_components = location_data.raw.get('address', {})
                return {
                    'address': location_data.address,
                    'city': address_components.get('city', ''),
                    'country': address_components.get('country', ''),
                    'postcode': address_components.get('postcode', '')
                }
            return None
        except Exception as e:
            print(f"Detailed address lookup failed: {e}")
            return None


class LocationService:
    """Service for handling location-related business operations"""
    
    def __init__(self):
        self.geocoding_service = GeocodingService()
    
    def create_location(self, latitude: float, longitude: float, amenity: str, description: str) -> location:
        """
        Create a new location with reverse geocoding
        
        Args:
            latitude (float): Latitude coordinate
            longitude (float): Longitude coordinate
            amenity (str): Type of amenity
            description (str): Description of the location
            
        Returns:
            location: Created location instance
        """
        # Get address from coordinates
        address = self.geocoding_service.get_address_from_coordinates(latitude, longitude)
        
        # Create and save the location
        location_instance = location.objects.create(
            latitude=latitude,
            longitude=longitude,
            amenity=amenity,
            description=description,
            address=address or "Address not available"
        )
        
        return location_instance
    
    def get_all_locations(self) -> List[location]:
        """
        Get all locations from the database
        
        Returns:
            List[location]: List of all location instances
        """
        return location.objects.all()
    
    def get_location_by_id(self, location_id: int) -> Optional[location]:
        """
        Get a location by its ID
        
        Args:
            location_id (int): ID of the location
            
        Returns:
            Optional[location]: Location instance or None if not found
        """
        try:
            return get_object_or_404(location, id=location_id)
        except:
            return None
    
    def upvote_location(self, location_id: int) -> Dict[str, Any]:
        """
        Increment the upvote count for a location
        
        Args:
            location_id (int): ID of the location to upvote
            
        Returns:
            Dict[str, Any]: Dictionary with upvote count and success status
        """
        location_instance = get_object_or_404(location, id=location_id)
        location_instance.upvoteCount += 1
        location_instance.save()
        
        return {
            'upvoteCount': location_instance.upvoteCount,
            'success': True
        }
    
    def get_coordinates_for_address(self, address: str) -> Optional[Dict[str, Any]]:
        """
        Get coordinates and formatted address for an address string
        
        Args:
            address (str): Address to geocode
            
        Returns:
            Optional[Dict[str, Any]]: Dictionary with coordinates and address or None
        """
        coordinates = self.geocoding_service.get_coordinates_from_address(address)
        if coordinates:
            # Also get the formatted address
            formatted_address = self.geocoding_service.get_address_from_coordinates(
                coordinates[0], coordinates[1]
            )
            return {
                'coordinates': list(coordinates),
                'address': formatted_address or address
            }
        return None
    
    def get_address_for_coordinates(self, latitude: float, longitude: float) -> Optional[Dict[str, Any]]:
        """
        Get detailed address information for coordinates
        
        Args:
            latitude (float): Latitude coordinate
            longitude (float): Longitude coordinate
            
        Returns:
            Optional[Dict[str, Any]]: Dictionary with detailed address info or None
        """
        return self.geocoding_service.get_detailed_address_info(latitude, longitude)


class LocationController:
    """Controller for handling location-related operations and coordinating between services and views"""
    
    def __init__(self):
        self.location_service = LocationService()
    
    def handle_location_form_submission(self, form_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Handle location form submission with validation and creation
        
        Args:
            form_data (Dict[str, Any]): Form data from POST request
            
        Returns:
            Dict[str, Any]: Result with success status and location info
        """
        from .forms import LocationForm
        
        form = LocationForm(form_data)
        if form.is_valid():
            cleaned_data = form.cleaned_data
            location_instance = self.location_service.create_location(
                latitude=cleaned_data['latitude'],
                longitude=cleaned_data['longitude'],
                amenity=cleaned_data['amenity'],
                description=cleaned_data['description']
            )
            return {
                'success': True,
                'location': location_instance,
                'redirect': 'success'
            }
        else:
            return {
                'success': False,
                'form': form,
                'errors': form.errors
            }
    
    def get_all_locations_for_display(self) -> Dict[str, Any]:
        """
        Get all locations formatted for display
        
        Returns:
            Dict[str, Any]: Dictionary with locations data
        """
        locations = self.location_service.get_all_locations()
        return {
            'locations': locations,
            'count': len(locations)
        }
    
    def handle_upvote(self, location_id: int) -> Dict[str, Any]:
        """
        Handle location upvote request
        
        Args:
            location_id (int): ID of location to upvote
            
        Returns:
            Dict[str, Any]: Dictionary with upvote result
        """
        try:
            result = self.location_service.upvote_location(location_id)
            return result
        except Exception as e:
            return {
                'success': False,
                'error': str(e)
            }
    
    def handle_geocoding_request(self, address: str) -> Dict[str, Any]:
        """
        Handle geocoding request for address
        
        Args:
            address (str): Address to geocode
            
        Returns:
            Dict[str, Any]: Dictionary with coordinates or error
        """
        result = self.location_service.get_coordinates_for_address(address)
        if result:
            return result
        else:
            return {'error': 'Address not found'}
    
    def handle_reverse_geocoding_request(self, latitude: float, longitude: float) -> Dict[str, Any]:
        """
        Handle reverse geocoding request for coordinates
        
        Args:
            latitude (float): Latitude coordinate
            longitude (float): Longitude coordinate
            
        Returns:
            Dict[str, Any]: Dictionary with address details or error
        """
        try:
            result = self.location_service.get_address_for_coordinates(latitude, longitude)
            if result:
                return result
            else:
                return {'error': 'Address not found'}
        except Exception as e:
            return {'error': str(e)}