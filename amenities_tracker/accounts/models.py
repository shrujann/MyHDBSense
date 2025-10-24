from django.db import models
from django.contrib.auth.models import AbstractUser

class CustomUser(AbstractUser):
    email = models.EmailField(unique=True)

    def __str__(self):
        return self.username
        
from django.conf import settings

GENDER_CHOICES = [
    ("male", "Male"),
    ("female", "Female"),
    ("other", "Other / Prefer not to say"),
]

RACE_CHOICES = [
    ("-", "No preference / Prefer not to say"),
    ("chinese", "Chinese"),
    ("malay", "Malay"),
    ("indian", "Indian"),
    ("other", "Other"),
]

class RoommateProfile(models.Model):
    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="roommate_profile")
    age = models.PositiveIntegerField(null=True, blank=True)
    gender = models.CharField(max_length=16, choices=GENDER_CHOICES, blank=True)
    race = models.CharField(max_length=16, choices=RACE_CHOICES, default="-", blank=True)
    max_budget = models.PositiveIntegerField(null=True, blank=True, help_text="Monthly max in SGD")
    preferred_neighbourhoods = models.JSONField(default=list, blank=True)
    is_looking = models.BooleanField(default=False)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"RoommateProfile<{self.user}>"

class ContactAttempt(models.Model):
    sender = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="sent_contacts")
    recipient = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="received_contacts")
    message = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)
