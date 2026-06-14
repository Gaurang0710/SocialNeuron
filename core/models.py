from django.conf import settings
from django.db import models

class BrandVoice(models.Model):
    name = models.CharField(max_length=100)
    document_content = models.TextField(help_text="Extracted text from old posts/documents to learn brand voice")
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.name

class PlatformIntegration(models.Model):
    platform = models.CharField(max_length=50, choices=[('slack', 'Slack'), ('discord', 'Discord'), ('email', 'Email')])
    webhook_url = models.URLField(blank=True, null=True)
    setup_email = models.EmailField(blank=True, null=True)
    is_active = models.BooleanField(default=True)

    def __str__(self):
        return self.platform


class EmailRecipient(models.Model):
    email = models.EmailField(unique=True)
    name = models.CharField(max_length=100, blank=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.email


class ContactInquiry(models.Model):
    STATUS_CHOICES = [
        ("new", "New"),
        ("in_progress", "In Progress"),
        ("closed", "Closed"),
    ]

    name = models.CharField(max_length=120)
    email = models.EmailField()
    company = models.CharField(max_length=120, blank=True)
    subject = models.CharField(max_length=200)
    message = models.TextField()
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="new")
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.name} - {self.subject}"

class PostSchedule(models.Model):
    STATUS_CHOICES = [
        ('draft', 'Draft'),
        ('pending', 'Pending'),
        ('approved', 'Approved'),
        ('rejected', 'Rejected'),
        ('scheduled', 'Scheduled'),
        ('published', 'Published'),
    ]

    date = models.DateTimeField()
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='posts', null=True, blank=True)
    topic = models.CharField(max_length=255)
    category = models.CharField(max_length=100)
    platform = models.CharField(max_length=100, default='LinkedIn')
    post_type = models.CharField(max_length=100, default='post')
    priority = models.CharField(max_length=50, default='Medium')
    published_link = models.URLField(blank=True, null=True)
    
    tone = models.CharField(max_length=50, blank=True, null=True)
    generated_content = models.TextField(blank=True, null=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='draft')
    
    # AI Scoring
    engagement_score = models.IntegerField(default=0, help_text="0-100")
    readability_score = models.IntegerField(default=0, help_text="0-100")
    virality_score = models.IntegerField(default=0, help_text="0-100")
    sentiment = models.CharField(max_length=50, blank=True, null=True)
    is_duplicate = models.BooleanField(default=False)
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.topic} - {self.platform} ({self.status})"

class ContentItem(models.Model):
    STATUS_CHOICES = [
        ('DRAFT', 'Draft'),
        ('APPROVED', 'Approved'),
        ('REJECTED', 'Rejected'),
    ]

    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='content_items')
    topic = models.CharField(max_length=255)
    platform = models.CharField(max_length=100)
    post_type = models.CharField(max_length=100)
    generated_content = models.TextField()
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='DRAFT')
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.topic} - {self.platform} ({self.status})"

class PostComment(models.Model):
    post = models.ForeignKey(PostSchedule, on_delete=models.CASCADE, related_name='comments')
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True)
    content = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Comment by {self.user} on {self.post.topic}"
# Additional field added safely via migration if needed
# We will just reuse category or priority as audience for simplicity, 
# or add it dynamically if we remakemigrations.
