from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.shortcuts import redirect, render

from .models import Profile

VALID_STRUCTURE_KEYS = dict(Profile.FAVORITE_STRUCTURE_CHOICES).keys()
MAX_AVATAR_BYTES = 2 * 1024 * 1024  # 2MB


@login_required
def profile(request):
    profile_obj, _ = Profile.objects.get_or_create(user=request.user)

    if request.method == "POST":
        if "remove_avatar" in request.POST:
            if profile_obj.avatar:
                profile_obj.avatar.delete(save=False)
                profile_obj.avatar = None
                profile_obj.save()
            messages.success(request, "Avatar removed.")
            return redirect("profile")

        bio = request.POST.get("bio", "").strip()[:140]
        favorite_structure = request.POST.get("favorite_structure", "")
        if favorite_structure not in VALID_STRUCTURE_KEYS:
            favorite_structure = ""

        avatar_file = request.FILES.get("avatar")
        if avatar_file:
            if avatar_file.size > MAX_AVATAR_BYTES:
                messages.error(request, "Avatar must be under 2MB.")
                return render(request, "profile/profile.html", {"profile_obj": profile_obj})
            if not avatar_file.content_type.startswith("image/"):
                messages.error(request, "Avatar must be an image file.")
                return render(request, "profile/profile.html", {"profile_obj": profile_obj})
            profile_obj.avatar = avatar_file

        profile_obj.bio = bio
        profile_obj.favorite_structure = favorite_structure
        profile_obj.save()
        messages.success(request, "Profile updated.")
        return redirect("profile")

    return render(request, "profile/profile.html", {"profile_obj": profile_obj})
