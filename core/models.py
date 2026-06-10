from django.db import models
from django.contrib.auth.models import User

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
    topic = models.CharField(max_length=255)
    category = models.CharField(max_length=100)
    platform = models.CharField(max_length=100, default='LinkedIn')
    priority = models.CharField(max_length=50, default='Medium')
    
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

class PostComment(models.Model):
    post = models.ForeignKey(PostSchedule, on_delete=models.CASCADE, related_name='comments')
    user = models.ForeignKey(User, on_delete=models.SET_NULL, null=True)
    content = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Comment by {self.user} on {self.post.topic}"
# Additional field added safely via migration if needed
# We will just reuse category or priority as audience for simplicity, 
# or add it dynamically if we remakemigrations.
