from django.contrib import admin

from users.models import BrandProfile, PasswordResetToken, User


class ReadOnlyUserDataAdmin(admin.ModelAdmin):
    """Allow user-owned support data to be inspected without direct edits."""

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False

    def has_view_permission(self, request, obj=None):
        return request.user.is_staff

    def get_readonly_fields(self, request, obj=None):
        return [field.name for field in self.model._meta.fields]


@admin.register(User)
class UserAdmin(admin.ModelAdmin):
    list_display = ("email", "is_active", "is_staff", "is_superuser", "created_at", "updated_at")
    search_fields = ("email",)
    list_filter = ("is_active", "is_staff", "is_superuser")
    readonly_fields = ("password", "last_login", "created_at", "updated_at")
    filter_horizontal = ("groups", "user_permissions")
    fieldsets = (
        ("Account", {
            "fields": ("email", "password", "last_login")
        }),
        ("Access", {
            "fields": ("is_active", "is_staff", "is_superuser", "groups", "user_permissions")
        }),
        ("Audit", {
            "fields": ("created_at", "updated_at")
        }),
    )

    def has_add_permission(self, request):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(BrandProfile)
class BrandProfileAdmin(ReadOnlyUserDataAdmin):
    list_display = ("brand_name", "niche", "tone", "user", "updated_at")
    search_fields = ("brand_name", "niche", "audience")
    autocomplete_fields = ("user",)


@admin.register(PasswordResetToken)
class PasswordResetTokenAdmin(ReadOnlyUserDataAdmin):
    list_display = ("user", "expires_at", "used_at", "created_at")
    list_filter = ("used_at",)
    autocomplete_fields = ("user",)
