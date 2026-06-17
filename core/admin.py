from django.contrib import admin
from .models import (
    BrandVoice,
    ContentItem,
    ContactInquiry,
    EmailRecipient,
    PlatformIntegration,
    PostSchedule,
    PromptTemplate,
)


admin.site.site_header = "SocialNEURON Administration"
admin.site.site_title = "SocialNEURON Admin"
admin.site.index_title = "Welcome to SocialNEURON Admin Panel"

@admin.register(PostSchedule)
class PostScheduleAdmin(admin.ModelAdmin):
    list_display = ('topic', 'platform', 'category', 'status', 'date', 'priority')
    list_filter = ('status', 'platform', 'category', 'priority')
    search_fields = ('topic', 'generated_content')
    autocomplete_fields = ('user',)


@admin.register(ContentItem)
class ContentItemAdmin(admin.ModelAdmin):
    list_display = ('topic', 'platform', 'post_type', 'status', 'created_at')
    list_filter = ('status', 'platform', 'post_type')
    search_fields = ('topic', 'generated_content')


@admin.register(BrandVoice)
class BrandVoiceAdmin(admin.ModelAdmin):
    list_display = ('name', 'created_at')
    search_fields = ('name', 'document_content')


@admin.register(PlatformIntegration)
class PlatformIntegrationAdmin(admin.ModelAdmin):
    list_display = ('platform', 'setup_email', 'is_active')
    list_filter = ('platform', 'is_active')


@admin.register(EmailRecipient)
class EmailRecipientAdmin(admin.ModelAdmin):
    list_display = ('email', 'name', 'is_active', 'created_at')
    list_filter = ('is_active',)
    search_fields = ('email', 'name')


@admin.register(ContactInquiry)
class ContactInquiryAdmin(admin.ModelAdmin):
    list_display = ('name', 'email', 'company', 'subject', 'status', 'created_at')
    list_filter = ('status', 'created_at')
    search_fields = ('name', 'email', 'company', 'subject', 'message')


@admin.register(PromptTemplate)
class PromptTemplateAdmin(admin.ModelAdmin):
    list_display = ('name', 'key', 'is_active', 'updated_at')
    list_filter = ('key', 'is_active')
    search_fields = ('name', 'key', 'description', 'template')
    readonly_fields = ('created_at', 'updated_at')
    fieldsets = (
        (None, {
            'fields': ('key', 'name', 'description', 'is_active')
        }),
        ('Prompt', {
            'fields': ('template',),
            'description': (
                'Available placeholders include {topic}, {query}, {platform}, {post_type}, '
                '{tone}, {audience}, {count}, {category}, {voice_context}, '
                '{platform_context}, {content_type_context}, {niche_context}, '
                '{goal_context}, {research_data}, {draft_content}, and {generated_content}.'
            ),
        }),
        ('Audit', {
            'fields': ('created_at', 'updated_at'),
        }),
    )
