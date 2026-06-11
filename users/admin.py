from django.contrib import admin

from users.models import BrandProfile, PasswordResetToken, User


@admin.register(User)
class UserAdmin(admin.ModelAdmin):
    list_display = ("email", "is_active", "is_staff", "created_at", "updated_at")
    search_fields = ("email",)
    list_filter = ("is_active", "is_staff")


@admin.register(BrandProfile)
class BrandProfileAdmin(admin.ModelAdmin):
    list_display = ("brand_name", "niche", "tone", "user", "updated_at")
    search_fields = ("brand_name", "niche", "audience")
    autocomplete_fields = ("user",)


@admin.register(PasswordResetToken)
class PasswordResetTokenAdmin(admin.ModelAdmin):
    list_display = ("user", "expires_at", "used_at", "created_at")
    list_filter = ("used_at",)
    autocomplete_fields = ("user",)
