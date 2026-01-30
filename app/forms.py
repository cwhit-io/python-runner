from django import forms
from django.contrib.auth.models import User
from .models import UserProfile


class UserProfileForm(forms.ModelForm):
    """Form for editing user profile."""

    # Add user fields
    first_name = forms.CharField(max_length=30, required=False)
    last_name = forms.CharField(max_length=30, required=False)
    email = forms.EmailField(required=True)

    class Meta:
        model = UserProfile
        fields = ["avatar", "bio", "theme_preference", "timezone", "time_format"]
        widgets = {
            "bio": forms.Textarea(
                attrs={"rows": 4, "class": "textarea textarea-bordered w-full"}
            ),
            "avatar": forms.FileInput(
                attrs={"class": "file-input file-input-bordered w-full"}
            ),
            "theme_preference": forms.Select(
                attrs={"class": "select select-bordered w-full"}
            ),
            "timezone": forms.Select(attrs={"class": "select select-bordered w-full"}),
            "time_format": forms.Select(
                attrs={"class": "select select-bordered w-full"}
            ),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.instance and self.instance.user:
            self.fields["first_name"].initial = self.instance.user.first_name
            self.fields["last_name"].initial = self.instance.user.last_name
            self.fields["email"].initial = self.instance.user.email

    def save(self, commit=True):
        profile = super().save(commit=False)

        # Update user fields
        user = profile.user
        user.first_name = self.cleaned_data["first_name"]
        user.last_name = self.cleaned_data["last_name"]
        user.email = self.cleaned_data["email"]

        if commit:
            user.save()
            profile.save()

        return profile
