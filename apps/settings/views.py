from django.contrib.auth import update_session_auth_hash
from django.contrib.auth.decorators import login_required
from django.contrib.auth.forms import PasswordChangeForm
from django.shortcuts import redirect, render
from django.urls import reverse


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
    return render(request, "settings/settings.html", {
        "password_form": password_form,
        "success": success,
    })
