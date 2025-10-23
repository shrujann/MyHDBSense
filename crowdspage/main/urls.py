from django.urls import path
from . import views

urlpatterns = [
    path('', views.mappage, name='mappage'),  # Root URL redirects to the map
    path('form/', views.form_view, name='form'),
    path('success/', views.success, name='success'),  #successfully submitted page
    path('results/', views.results_view, name='results'),
    path('upvote/<int:location_id>/', views.upvote_location, name='upvote_location'),
    path('get-coordinates/', views.get_coordinates, name='get_coordinates'),
    path('get-address/', views.get_address, name='get_address'), 
]