#apps/profile/models.py
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

    THEME_CHOICES = [
        ("dark", "Dark"),
        ("light", "Light"),
    ]

    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name="profile")
    bio = models.CharField(max_length=140, blank=True)
    favorite_structure = models.CharField(
        max_length=20, choices=FAVORITE_STRUCTURE_CHOICES, blank=True
    )
    avatar = models.ImageField(upload_to="avatars/", blank=True, null=True)
    theme = models.CharField(max_length=10, choices=THEME_CHOICES, default="dark")

    def __str__(self):
        return f"{self.user.username}'s profile"

    @property
    def structure_progress(self):
        """Every structure in the roadmap, flagged as the current favorite or not.
        Placeholder for real per-structure trace stats once tracing is built."""
        return [
            {"key": key, "label": label, "is_favorite": key == self.favorite_structure}
            for key, label in self.FAVORITE_STRUCTURE_CHOICES
            if key
        ]


@receiver(post_save, sender=User)
def create_profile_for_new_user(sender, instance, created, **kwargs):
    if created:
        Profile.objects.get_or_create(user=instance)
