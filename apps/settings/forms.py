# apps/settings/forms.py
from django.contrib.auth import get_user_model
from django.contrib.auth.validators import ASCIIUsernameValidator
from django import forms

User = get_user_model()


class UsernameChangeForm(forms.Form):
    username = forms.CharField(
        max_length=150,
        validators=[ASCIIUsernameValidator()],
        help_text="Letters, digits and @/./+/-/_ only.",
    )

    def __init__(self, *args, current_user=None, **kwargs):
        self.current_user = current_user
        super().__init__(*args, **kwargs)

    def clean_username(self):
        username = self.cleaned_data["username"]
        if username == self.current_user.username:
            raise forms.ValidationError("That's already your username.")
        if User.objects.filter(username__iexact=username).exclude(pk=self.current_user.pk).exists():
            raise forms.ValidationError("That username is already taken.")
        return username


class DeleteAccountForm(forms.Form):
    password = forms.CharField(widget=forms.PasswordInput)
    confirm = forms.CharField(
        help_text='Type "delete my account" to confirm.',
    )

    def __init__(self, *args, user=None, **kwargs):
        self.user = user
        super().__init__(*args, **kwargs)

    def clean_password(self):
        password = self.cleaned_data["password"]
        if not self.user.check_password(password):
            raise forms.ValidationError("Incorrect password.")
        return password

    def clean_confirm(self):
        confirm = self.cleaned_data["confirm"]
        if confirm.strip().lower() != "delete my account":
            raise forms.ValidationError('Please type "delete my account" exactly.')
        return confirm
