from django.shortcuts import render


# Create your views here.
from django.contrib.auth.forms import PasswordChangeForm
from django.contrib.auth import update_session_auth_hash
from django.urls import reverse
from django.shortcuts import render, redirect
from django.contrib.auth import login
from django.contrib.auth.forms import UserCreationForm

# added
from django.contrib.auth.decorators import login_required
from django.shortcuts import redirect, render
from .models import Profile
VALID_STRUCTURE_KEYS = dict(Profile.FAVORITE_STRUCTURE_CHOICES).keys()

def landing(request):
    return render(request, "landing.html")

def register(request):
    if request.method == "POST":
        form = UserCreationForm(request.POST)
        if form.is_valid():
            user = form.save()
            login(request, user)
            return redirect("landing")
    else:
        form = UserCreationForm()
    return render(request, "accounts/register.html", {"form": form})

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
 
    return render(request, "accounts/profile.html", {"profile_obj": profile_obj})


@login_required
def account_settings(request):
    password_form = PasswordChangeForm(request.user)

    if request.method == "POST":
        if "update_email" in request.POST:
            email = request.POST.get("email", "").strip()
            request.user.email = email
            request.user.save()
            return redirect(f"{reverse('settings')}?success=email")

        elif "change_password" in request.POST:
            password_form = PasswordChangeForm(request.user, request.POST)
            if password_form.is_valid():
                user = password_form.save()
                # keeps the user logged in after a password change,
                # instead of Django logging them out automatically
                update_session_auth_hash(request, user)
                return redirect(f"{reverse('settings')}?success=password")

    success = request.GET.get("success")
    return render(request, "accounts/settings.html", {
        "password_form": password_form,
        "success": success,
    })