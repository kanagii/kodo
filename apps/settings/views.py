from django.contrib import messages
from django.contrib.auth import logout, update_session_auth_hash
from django.contrib.auth.decorators import login_required
from django.contrib.auth.forms import PasswordChangeForm
from django.shortcuts import redirect, render
from django.urls import reverse

from apps.profile.models import Profile

from .forms import DeleteAccountForm, UsernameChangeForm


@login_required
def account_settings(request):
    password_form = PasswordChangeForm(request.user)
    username_form = UsernameChangeForm(current_user=request.user)
    delete_form = DeleteAccountForm(user=request.user)
    profile_obj, _ = Profile.objects.get_or_create(user=request.user)

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
                update_session_auth_hash(request, user)
                return redirect(f"{reverse('settings')}?success=password")

        elif "change_username" in request.POST:
            username_form = UsernameChangeForm(request.POST, current_user=request.user)
            if username_form.is_valid():
                request.user.username = username_form.cleaned_data["username"]
                request.user.save()
                update_session_auth_hash(request, request.user)
                return redirect(f"{reverse('settings')}?success=username")

        elif "change_theme" in request.POST:
            theme = request.POST.get("theme")
            if theme in dict(Profile.THEME_CHOICES):
                profile_obj.theme = theme
                profile_obj.save()
            return redirect(f"{reverse('settings')}?success=theme")

        elif "delete_account" in request.POST:
            delete_form = DeleteAccountForm(request.POST, user=request.user)
            if delete_form.is_valid():
                user = request.user
                logout(request)
                user.delete()
                messages.success(request, "Your account has been deleted.")
                return redirect("landing")

    success = request.GET.get("success")
    return render(request, "settings/settings.html", {
        "password_form": password_form,
        "username_form": username_form,
        "delete_form": delete_form,
        "profile_obj": profile_obj,
        "success": success,
    })
