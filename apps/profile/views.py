from django.contrib.auth.decorators import login_required
from django.shortcuts import redirect, render

from .models import Profile

VALID_STRUCTURE_KEYS = dict(Profile.FAVORITE_STRUCTURE_CHOICES).keys()


@login_required
def profile(request):
    # get_or_create as a safety net for accounts that existed before
    # the Profile model/signal were added.
    profile_obj, _ = Profile.objects.get_or_create(user=request.user)

    if request.method == "POST":
        bio = request.POST.get("bio", "").strip()[:140]
        favorite_structure = request.POST.get("favorite_structure", "")
        if favorite_structure not in VALID_STRUCTURE_KEYS:
            favorite_structure = ""

        profile_obj.bio = bio
        profile_obj.favorite_structure = favorite_structure
        profile_obj.save()
        return redirect("profile")

    return render(request, "profile/profile.html", {"profile_obj": profile_obj})
