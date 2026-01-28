from django.contrib import admin
from django.utils.html import format_html
from .models import (
    APILog,
    UserProfile,
    APIToken,
    Script,
    ScriptExecution,
    ScriptSchedule,
    Tag,
)
from unfold.admin import ModelAdmin


@admin.register(UserProfile)
class UserProfileAdmin(ModelAdmin):
    """Admin interface for user profiles."""

    list_display = ["user", "email_verified", "theme_preference", "created_at"]
    list_filter = ["email_verified", "theme_preference", "created_at"]
    search_fields = ["user__username", "user__email", "bio"]
    readonly_fields = ["created_at", "updated_at", "email_verification_token"]

    fieldsets = (
        ("User", {"fields": ("user",)}),
        ("Profile Information", {"fields": ("avatar", "bio")}),
        ("Preferences", {"fields": ("theme_preference",)}),
        ("Verification", {"fields": ("email_verified", "email_verification_token")}),
        (
            "Timestamps",
            {"fields": ("created_at", "updated_at"), "classes": ("collapse",)},
        ),
    )


@admin.register(APIToken)
class APITokenAdmin(ModelAdmin):
    """Admin interface for API tokens."""

    list_display = ["user", "name", "is_active", "created_at", "last_used"]
    list_filter = ["is_active", "created_at"]
    search_fields = ["user__username", "name", "token"]
    readonly_fields = ["token", "created_at", "last_used"]

    fieldsets = (
        ("Token Information", {"fields": ("user", "name", "token", "is_active")}),
        ("Usage", {"fields": ("created_at", "last_used")}),
    )

    def has_change_permission(self, request, obj=None):
        """Users can only deactivate tokens, not change them."""
        return True


@admin.register(APILog)
class APILogAdmin(ModelAdmin):
    """Admin interface for API logs."""

    class Media:
        css = {"all": ("css/admin-custom.css",)}

    list_display = [
        "timestamp",
        "method_colored",
        "path",
        "status_code_colored",
        "user",
        "duration_display",
        "ip_address",
    ]

    list_filter = [
        "method",
        "status_code",
        "timestamp",
        "user",
    ]

    search_fields = [
        "path",
        "full_path",
        "user__username",
        "ip_address",
        "query_params",
        "error",
    ]

    readonly_fields = [
        "timestamp",
        "method",
        "path",
        "full_path",
        "user",
        "ip_address",
        "user_agent",
        "query_params",
        "request_body",
        "status_code",
        "response_body",
        "duration_ms",
        "error",
    ]

    fieldsets = (
        (
            "Request Information",
            {
                "fields": (
                    "timestamp",
                    "method",
                    "path",
                    "full_path",
                    "query_params",
                    "request_body",
                )
            },
        ),
        (
            "User Information",
            {
                "fields": (
                    "user",
                    "ip_address",
                    "user_agent",
                )
            },
        ),
        (
            "Response Information",
            {
                "fields": (
                    "status_code",
                    "response_body",
                    "duration_ms",
                )
            },
        ),
        (
            "Error Details",
            {
                "fields": ("error",),
                "classes": ("collapse",),
            },
        ),
    )

    date_hierarchy = "timestamp"

    def has_add_permission(self, request):
        """Disable adding logs manually."""
        return False

    def has_change_permission(self, request, obj=None):
        """Disable editing logs."""
        return False

    @admin.display(description="Method", ordering="method")
    def method_colored(self, obj):
        """Display HTTP method with color coding."""
        colors = {
            "GET": "#28a745",
            "POST": "#007bff",
            "PUT": "#ffc107",
            "PATCH": "#fd7e14",
            "DELETE": "#dc3545",
        }
        color = colors.get(obj.method, "#6c757d")
        return format_html(
            '<span style="color: {}; font-weight: bold;">{}</span>', color, obj.method
        )

    @admin.display(description="Status", ordering="status_code")
    def status_code_colored(self, obj):
        """Display status code with color coding."""
        if not obj.status_code:
            return "-"

        if obj.status_code < 300:
            color = "#28a745"  # Success - green
        elif obj.status_code < 400:
            color = "#17a2b8"  # Redirect - cyan
        elif obj.status_code < 500:
            color = "#ffc107"  # Client error - yellow
        else:
            color = "#dc3545"  # Server error - red

        return format_html(
            '<span style="color: {}; font-weight: bold;">{}</span>',
            color,
            obj.status_code,
        )

    @admin.display(description="Duration", ordering="duration_ms")
    def duration_display(self, obj):
        """Display duration with formatting."""
        if not obj.duration_ms:
            return "-"

        if obj.duration_ms < 100:
            color = "#28a745"  # Fast - green
        elif obj.duration_ms < 1000:
            color = "#ffc107"  # Medium - yellow
        else:
            color = "#dc3545"  # Slow - red

        return format_html(
            '<span style="color: {};">{}ms</span>', color, f"{obj.duration_ms:.2f}"
        )

    def get_queryset(self, request):
        """Optimize queryset with select_related."""
        qs = super().get_queryset(request)
        return qs.select_related("user")


@admin.register(Tag)
class TagAdmin(ModelAdmin):
    """Admin interface for tags."""

    list_display = ["name", "color_display", "created_by", "script_count", "created_at"]
    list_filter = ["created_at", "created_by"]
    search_fields = ["name", "description"]
    readonly_fields = ["created_at"]

    fieldsets = (
        ("Tag Information", {"fields": ("name", "color", "description", "created_by")}),
        ("Timestamps", {"fields": ("created_at",), "classes": ("collapse",)}),
    )

    @admin.display(description="Color")
    def color_display(self, obj):
        """Display color as a colored square."""
        return format_html(
            '<div style="width: 20px; height: 20px; background-color: {}; border: 1px solid #ccc; display: inline-block;"></div> {}',
            obj.color,
            obj.color,
        )

    @admin.display(description="Scripts")
    def script_count(self, obj):
        """Display number of scripts with this tag."""
        return obj.scripts.count()


@admin.register(Script)
class ScriptAdmin(ModelAdmin):
    """Admin interface for scripts."""

    list_display = [
        "name",
        "owner",
        "last_status",
        "execution_count",
        "last_run",
        "is_public",
        "tag_list",
        "created_at",
    ]
    list_filter = ["last_status", "is_public", "created_at", "owner", "tags"]
    search_fields = ["name", "description", "owner__username"]
    readonly_fields = [
        "venv_path",
        "venv_created",
        "venv_updated_at",
        "execution_count",
        "last_run",
        "last_success",
        "created_at",
        "updated_at",
    ]

    fieldsets = (
        ("Basic Information", {"fields": ("name", "description", "owner", "tags")}),
        ("Code", {"fields": ("code", "dependencies")}),
        (
            "Virtual Environment",
            {
                "fields": ("venv_path", "venv_created", "venv_updated_at"),
                "classes": ("collapse",),
            },
        ),
        (
            "Status",
            {"fields": ("last_status", "last_run", "last_success", "execution_count")},
        ),
        ("Permissions", {"fields": ("is_public",)}),
        (
            "Timestamps",
            {"fields": ("created_at", "updated_at"), "classes": ("collapse",)},
        ),
    )

    @admin.display(description="Tags")
    def tag_list(self, obj):
        """Display tags as colored badges."""
        tags = obj.tags.all()
        if not tags:
            return "-"

        tag_html = []
        for tag in tags:
            tag_html.append(
                format_html(
                    '<span style="background-color: {}; color: white; padding: 2px 6px; border-radius: 3px; font-size: 11px; margin-right: 4px;">{}</span>',
                    tag.color,
                    tag.name,
                )
            )
        return format_html("".join(tag_html))


@admin.register(ScriptExecution)
class ScriptExecutionAdmin(ModelAdmin):
    """Admin interface for script executions."""

    list_display = [
        "script",
        "status",
        "trigger_type",
        "triggered_by",
        "started_at",
        "duration_seconds",
        "exit_code",
    ]
    list_filter = ["status", "trigger_type", "created_at"]
    search_fields = ["script__name", "triggered_by__username", "stdout", "stderr"]
    readonly_fields = [
        "script",
        "triggered_by",
        "status",
        "started_at",
        "completed_at",
        "duration_seconds",
        "stdout",
        "stderr",
        "exit_code",
        "error_message",
        "process_id",
        "created_at",
        "trigger_type",
    ]

    fieldsets = (
        (
            "Execution Info",
            {"fields": ("script", "triggered_by", "trigger_type", "status")},
        ),
        (
            "Timing",
            {
                "fields": (
                    "created_at",
                    "started_at",
                    "completed_at",
                    "duration_seconds",
                )
            },
        ),
        ("Output", {"fields": ("stdout", "stderr", "exit_code", "error_message")}),
        ("Process", {"fields": ("process_id",), "classes": ("collapse",)}),
    )

    def has_add_permission(self, request):
        """Disable manual addition."""
        return False

    def has_change_permission(self, request, obj=None):
        """Read-only."""
        return False


@admin.register(ScriptSchedule)
class ScriptScheduleAdmin(ModelAdmin):
    """Admin interface for script schedules."""

    list_display = [
        "name",
        "script",
        "cron_expression",
        "is_active",
        "last_run",
        "next_run",
        "created_at",
    ]
    list_filter = ["is_active", "created_at"]
    search_fields = ["name", "script__name", "cron_expression"]
    readonly_fields = ["last_run", "next_run", "created_at", "updated_at"]

    fieldsets = (
        ("Basic Information", {"fields": ("name", "script", "created_by")}),
        ("Schedule", {"fields": ("cron_expression", "timezone", "is_active")}),
        ("Status", {"fields": ("last_run", "next_run")}),
        (
            "Timestamps",
            {"fields": ("created_at", "updated_at"), "classes": ("collapse",)},
        ),
    )
