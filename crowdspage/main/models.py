from django.db import models

# Create your models here.
class location(models.Model):
    latitude = models.FloatField()
    longitude = models.FloatField()
    address = models.CharField(max_length=500, blank=True, null=True)
    amenity = models.CharField(max_length=100)
    description = models.TextField()
    upvoteCount = models.IntegerField(default=0)

    def number_of_upvotes(self):
        return self.upvoteCount

    def get_coordinates(self):
        return (self.latitude, self.longitude)
    
    def __str__(self):
        return f"{self.amenity} at {self.address or 'Location not known'}"

