from django.shortcuts import render, redirect, get_object_or_404
from django.http import JsonResponse
from django.core.files.storage import FileSystemStorage
from django.contrib import messages
from django.conf import settings
from django.core.mail import send_mail
from django.core.validators import validate_email
from django.core.exceptions import ValidationError
from django.utils import timezone
from datetime import datetime, time
from .models import EmailRecipient, PostComment, PostSchedule
from .tasks import generate_post_draft
from .services.content_generation import generate_topic_ideas
from .services.schedule_import import import_schedule_file

def dashboard(request):
    posts = PostSchedule.objects.all()
    recent = posts.order_by('-updated_at')[:5]
    context = {
        'total': posts.count(),
        'pending': posts.filter(status='pending').count(),
        'approved': posts.filter(status='approved').count(),
        'published': posts.filter(status='published').count(),
        'draft': posts.filter(status='draft').count(),
        'rejected': posts.filter(status='rejected').count(),
        'upcoming': posts.filter(status__in=['draft', 'pending', 'approved']).order_by('date')[:8],
        'recent': recent,
    }
    return render(request, 'core/dashboard.html', context)

def generate_topics_view(request):
    if request.method == 'POST':
        query = request.POST.get('query', 'IT and Startup')
        tone = request.POST.get('tone', 'Professional')
        audience = request.POST.get('audience', 'General')

        generated, error = generate_topic_ideas(query, tone, audience)
        if error:
            return render(request, 'core/partials/topic_results.html', {
                'topics': [],
                'error': error,
            })
        return render(request, 'core/partials/topic_results.html', {'topics': generated})

    posts = PostSchedule.objects.all()
    return render(request, 'core/topic_generator.html', {
        'draft_count': posts.filter(status='draft').count(),
        'pending_count': posts.filter(status='pending').count(),
        'approved_count': posts.filter(status='approved').count(),
        'published_count': posts.filter(status='published').count(),
    })


def save_generated_topic(request):
    if request.method != 'POST':
        return redirect('generate_topics')

    title = request.POST.get('title', '').strip()
    if not title:
        messages.error(request, "Topic title is required.")
        return redirect('generate_topics')

    PostSchedule.objects.create(
        date=timezone.now() + timezone.timedelta(days=1),
        topic=title,
        tone=request.POST.get('tone') or 'Professional',
        category=request.POST.get('audience') or 'General',
        platform='LinkedIn',
        priority='Medium',
        status='draft',
    )
    messages.success(request, "Topic added to Drafts. Run Cron Manually to generate the LinkedIn post.")
    return redirect('dashboard')

def upload_csv(request):
    if request.method == 'POST' and request.FILES.get('file'):
        file = request.FILES['file']
        fs = FileSystemStorage()
        name = fs.save(file.name, file)
        try:
            created_count = import_schedule_file(fs.path(name))
            fs.delete(name)
            messages.success(request, f"Uploaded {created_count} scheduled LinkedIn topics.")
        except Exception as exc:
            messages.error(request, f"Upload failed: {exc}")
        return redirect('dashboard')
    return render(request, 'core/upload.html')


def email_integration(request):
    if request.method == 'POST':
        raw_emails = request.POST.get('emails', '')
        name = request.POST.get('name', '').strip()
        emails = [
            email.strip().lower()
            for chunk in raw_emails.replace('\n', ',').split(',')
            for email in chunk.split()
            if email.strip()
        ]

        created_count = 0
        invalid_emails = []
        for email in emails:
            try:
                validate_email(email)
            except ValidationError:
                invalid_emails.append(email)
                continue

            recipient, created = EmailRecipient.objects.get_or_create(
                email=email,
                defaults={'name': name, 'is_active': True},
            )
            if not created and not recipient.is_active:
                recipient.is_active = True
                if name and not recipient.name:
                    recipient.name = name
                recipient.save(update_fields=['is_active', 'name'])
            created_count += int(created)

        if created_count or emails:
            messages.success(request, f"Saved {len(emails) - len(invalid_emails)} active email recipient(s).")
        if invalid_emails:
            messages.error(request, "Invalid email(s): " + ", ".join(invalid_emails))
        return redirect('email_integration')

    recipients = EmailRecipient.objects.order_by('-is_active', 'email')
    return render(request, 'core/email_integration.html', {
        'recipients': recipients,
        'active_count': recipients.filter(is_active=True).count(),
        'fallback_email': settings.DEMO_RECIPIENT_EMAIL,
    })


def toggle_email_recipient(request, recipient_id):
    recipient = get_object_or_404(EmailRecipient, id=recipient_id)
    recipient.is_active = not recipient.is_active
    recipient.save(update_fields=['is_active'])
    messages.success(request, f"{'Enabled' if recipient.is_active else 'Disabled'} {recipient.email}.")
    return redirect('email_integration')

def review_dashboard(request):
    pending = PostSchedule.objects.filter(status='pending').order_by('date')
    approved = PostSchedule.objects.filter(status='approved').order_by('date')
    rejected = PostSchedule.objects.filter(status='rejected').order_by('date')
    return render(request, 'core/review_dashboard.html', {
        'pending': pending, 'approved': approved, 'rejected': rejected
    })

def approve_post(request, post_id):
    p = get_object_or_404(PostSchedule, id=post_id)
    p.status = 'approved'
    p.save()
    return redirect('review_dashboard')

def reject_post(request, post_id):
    p = get_object_or_404(PostSchedule, id=post_id)
    p.status = 'rejected'
    p.save()
    return redirect('review_dashboard')

def regenerate_post(request, post_id):
    post = get_object_or_404(PostSchedule, id=post_id)
    generate_post_draft(post.id)
    messages.success(request, f"Regenerated content for '{post.topic}'.")
    return redirect('review_dashboard')

def history_view(request):
    published = PostSchedule.objects.filter(status='published').order_by('-date')
    return render(request, 'core/history.html', {'published': published})

def trigger_cron(request):
    today = timezone.localdate()
    tomorrow = today + timezone.timedelta(days=1)
    window_start = timezone.make_aware(datetime.combine(today, time.min))
    window_end = timezone.make_aware(datetime.combine(tomorrow + timezone.timedelta(days=1), time.min))

    due_posts = PostSchedule.objects.filter(
        status__in=['draft', 'pending'],
        date__gte=window_start,
        date__lt=window_end,
    ).order_by('date')

    generated_count = 0
    alerted_count = 0
    mail_errors = []
    for scheduled_post in due_posts:
        post = scheduled_post
        if scheduled_post.status == 'draft':
            post = generate_post_draft(scheduled_post.id)
            if post:
                generated_count += 1

        if post:
            sent, error = _send_review_email(post)
            if sent:
                alerted_count += 1
            elif error:
                mail_errors.append(error)

    approved = PostSchedule.objects.filter(status='approved', date__lte=timezone.now())
    published_count = approved.count()
    approved.update(status='published')

    if due_posts.exists():
        messages.success(
            request,
            f"Cron checked today and tomorrow: generated {generated_count} draft(s), "
            f"sent {alerted_count} Gmail alert(s) to {', '.join(_get_alert_recipients())}, "
            f"and published {published_count} approved post(s).",
        )
    else:
        messages.error(
            request,
            f"No draft or pending LinkedIn posts found for today or tomorrow. "
            f"Published {published_count} approved post(s) that were due.",
        )
    if mail_errors:
        messages.error(request, f"Gmail alert failed: {mail_errors[0]}")
    return redirect('review_dashboard')


def post_detail(request, post_id):
    post = get_object_or_404(PostSchedule, id=post_id)
    if request.method == 'POST':
        content = request.POST.get('content', '').strip()
        if content:
            PostComment.objects.create(post=post, user=request.user if request.user.is_authenticated else None, content=content)
            messages.success(request, "Comment added.")
        return redirect('post_detail', post_id=post.id)
    return render(request, 'core/post_detail.html', {'post': post})


def advanced_ai_action(request, post_id, tool):
    post = get_object_or_404(PostSchedule, id=post_id)
    prompts = {
        'hashtag': f"Suggest 8 LinkedIn hashtags for this topic: {post.topic}",
        'hook': f"Write 5 stronger LinkedIn hooks for this post topic: {post.topic}",
        'rewrite': f"Rewrite this LinkedIn post in a sharper professional tone:\n\n{post.generated_content}",
    }
    from .services.ai_client import ask_ollama
    return JsonResponse({'result': ask_ollama(prompts.get(tool, prompts['rewrite']))})


def _send_review_email(post):
    recipients = _get_alert_recipients()
    try:
        sent_count = send_mail(
            subject=f"LinkedIn draft ready for review: {post.topic}",
            message=(
                f"Your AI-generated LinkedIn draft is ready for review.\n\n"
                f"Scheduled date: {post.date:%Y-%m-%d %H:%M}\n"
                f"Audience: {post.category}\n"
                f"Tone: {post.tone or 'Professional'}\n"
                f"Score: {post.engagement_score}/100\n\n"
                f"{post.generated_content}\n\n"
                "Open the Review Center to approve, reject, or regenerate this draft."
            ),
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=recipients,
            fail_silently=False,
        )
    except Exception as exc:
        return False, str(exc)
    return sent_count > 0, None


def _get_alert_recipients():
    recipients = list(
        EmailRecipient.objects.filter(is_active=True).values_list('email', flat=True)
    )
    return recipients or [settings.DEMO_RECIPIENT_EMAIL]
