"""
URL configuration for app project.

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/6.0/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  path('', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  path('', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.urls import include, path
    2. Add a URL to urlpatterns:  path('blog/', include('blog.urls'))
"""

from django.contrib import admin
from django.urls import path, include
from django.contrib.auth import views as auth_views
from django.conf import settings
from django.conf.urls.static import static
from . import views
from . import views_scripts
from .api import api

urlpatterns = [
    path("", views_scripts.scripts_list, name="index"),
    path("websocket-demo/", views.websocket_demo, name="websocket_demo"),
    # Authentication
    path("login/", auth_views.LoginView.as_view(), name="login"),
    path("logout/", auth_views.LogoutView.as_view(next_page="/"), name="logout"),
    path("register/", views.register_view, name="register"),
    # Password Reset
    path(
        "password-reset/",
        auth_views.PasswordResetView.as_view(
            template_name="registration/password_reset_form.html"
        ),
        name="password_reset",
    ),
    path(
        "password-reset/done/",
        auth_views.PasswordResetDoneView.as_view(
            template_name="registration/password_reset_done.html"
        ),
        name="password_reset_done",
    ),
    path(
        "password-reset-confirm/<uidb64>/<token>/",
        auth_views.PasswordResetConfirmView.as_view(
            template_name="registration/password_reset_confirm.html"
        ),
        name="password_reset_confirm",
    ),
    path(
        "password-reset-complete/",
        auth_views.PasswordResetCompleteView.as_view(
            template_name="registration/password_reset_complete.html"
        ),
        name="password_reset_complete",
    ),
    # Email Verification
    path("verify-email/<str:token>/", views.verify_email, name="verify_email"),
    path("resend-verification/", views.resend_verification, name="resend_verification"),
    # User Profile
    path("profile/", views.profile, name="profile"),
    path("profile/edit/", views.profile_edit, name="profile_edit"),
    path("update-theme/", views.update_theme, name="update_theme"),
    # API Tokens
    path("api-tokens/", views.api_tokens, name="api_tokens"),
    path("api-tokens/create/", views.create_api_token, name="create_api_token"),
    path(
        "api-tokens/<int:token_id>/toggle/",
        views.toggle_api_token,
        name="toggle_api_token",
    ),
    path(
        "api-tokens/<int:token_id>/delete/",
        views.delete_api_token,
        name="delete_api_token",
    ),
    # Scripts
    path("scripts/", views_scripts.scripts_list, name="scripts_list"),
    path("scripts/create/", views_scripts.script_create, name="script_create"),
    path("scripts/<int:script_id>/", views_scripts.script_detail, name="script_detail"),
    path(
        "scripts/<int:script_id>/edit/", views_scripts.script_edit, name="script_edit"
    ),
    path(
        "scripts/<int:script_id>/duplicate/",
        views_scripts.script_duplicate,
        name="script_duplicate",
    ),
    path(
        "scripts/<int:script_id>/delete/",
        views_scripts.script_delete,
        name="script_delete",
    ),
    path(
        "scripts/<int:script_id>/export/",
        views_scripts.script_export,
        name="script_export",
    ),
    path(
        "scripts/<int:script_id>/execute/",
        views_scripts.script_execute,
        name="script_execute",
    ),
    path(
        "scripts/bulk-delete/",
        views_scripts.scripts_bulk_delete,
        name="scripts_bulk_delete",
    ),
    path("scripts/import/", views_scripts.script_import, name="script_import"),
    path(
        "executions/<int:execution_id>/",
        views_scripts.execution_detail,
        name="execution_detail",
    ),
    path(
        "executions/<int:execution_id>/kill/",
        views_scripts.execution_kill,
        name="execution_kill",
    ),
    # Tags
    path("tags/", views_scripts.tags_list, name="tags_list"),
    path("tags/create/", views_scripts.tag_create, name="tag_create"),
    path("tags/<int:tag_id>/edit/", views_scripts.tag_edit, name="tag_edit"),
    path("tags/<int:tag_id>/delete/", views_scripts.tag_delete, name="tag_delete"),
    # Schedules
    path(
        "scripts/<int:script_id>/schedules/create/",
        views_scripts.schedule_create,
        name="schedule_create",
    ),
    # Script secrets (owner-only JSON endpoints)
    path(
        "scripts/<int:script_id>/secrets/",
        views_scripts.script_secrets_list,
        name="script_secrets_list",
    ),
    path(
        "scripts/<int:script_id>/secrets/set/",
        views_scripts.script_secret_set,
        name="script_secret_set",
    ),
    path(
        "scripts/<int:script_id>/secrets/delete/",
        views_scripts.script_secret_delete,
        name="script_secret_delete",
    ),
    path(
        "scripts/<int:script_id>/secrets/get/",
        views_scripts.script_secret_get,
        name="script_secret_get",
    ),
    path(
        "schedules/<int:schedule_id>/toggle/",
        views_scripts.schedule_toggle,
        name="schedule_toggle",
    ),
    path(
        "schedules/<int:schedule_id>/delete/",
        views_scripts.schedule_delete,
        name="schedule_delete",
    ),
    # htmx endpoints
    path("items/", views.list_items_htmx, name="items-list-htmx"),
    path("items/add/", views.add_item_htmx, name="add-item-htmx"),
    path(
        "items/<int:item_id>/delete/", views.delete_item_htmx, name="delete-item-htmx"
    ),
    # API endpoints
    path("api/", api.urls),
    path("admin/", admin.site.urls),
]

# Serve media files in development
if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
