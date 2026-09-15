from django.contrib.auth.models import User
from django.db import models
from django.db.models.signals import post_save
from django.dispatch import receiver


class Profile(models.Model):
    FAVORITE_STRUCTURE_CHOICES = [
        ("", "Not set yet"),
        ("array", "Arrays"),
        ("linked_list", "Linked Lists"),
        ("stack", "Stacks"),
        ("queue", "Queues"),
        ("tree", "Trees"),
        ("graph", "Graphs"),
    ]

    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name="profile")
    bio = models.CharField(max_length=140, blank=True)
    favorite_structure = models.CharField(
        max_length=20, choices=FAVORITE_STRUCTURE_CHOICES, blank=True
    )

    def __str__(self):
        return f"{self.user.username}'s profile"


# Automatically creates a Profile row whenever a new User registers,
# so you never have to remember to create one manually.
@receiver(post_save, sender=User)
def create_profile_for_new_user(sender, instance, created, **kwargs):
    if created:
        Profile.objects.get_or_create(user=instance)
