from django import forms
from .models import location

#creating a location form
class LocationForm(forms.ModelForm):
    class Meta:
        model = location  # Link the form to the Location model
        fields = ['latitude', 'longitude', 'amenity', 'description']  # Fields to include in the form

