from django.db import models
from django.contrib.auth.models import AbstractUser
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

class CustomUser(AbstractUser):
    email = models.EmailField(unique=True)

    def __str__(self):
        return self.username

class RoommateProfile(models.Model):
    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    display_name = models.CharField(max_length=100, blank=True)
    age_range = models.CharField(
        max_length=20,
        choices=[
            ('18-24', '18-24 years'),
            ('25-34', '25-34 years'),
            ('35-44', '35-44 years'),
            ('45+', '45+ years')
        ],
        default='25-34'
    )
    gender = models.CharField(max_length=10, choices=GENDER_CHOICES)
    occupation = models.CharField(
        max_length=20,
        choices=[
            ('student', 'Student'),
            ('working', 'Working Professional'),
            ('other', 'Other')
        ],
        default='working'
    )
    lifestyle = models.CharField(
        max_length=20,
        choices=[
            ('early_bird', 'Early Bird'),
            ('night_owl', 'Night Owl'),
            ('flexible', 'Flexible')
        ],
        default='flexible'
    )
    neighbourhoods_csv = models.TextField(help_text="Comma-separated list of preferred neighborhoods", null=True, blank=True)
    budget = models.DecimalField(max_digits=8, decimal_places=2, default=0)
    is_looking = models.BooleanField(default=True)
    
    def __str__(self):
        return f"{self.user.username}'s Profile"

class ContactAttempt(models.Model):
    sender = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="sent_contacts")
    recipient = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="received_contacts")
    message = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)