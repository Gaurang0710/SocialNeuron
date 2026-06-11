"""Django views for the SaaS-ready content automation app."""
from __future__ import annotations

from datetime import datetime, time, timedelta

from django.conf import settings
from django.contrib import messages
from django.core.exceptions import ValidationError
from django.core.files.storage import FileSystemStorage
from django.core.mail import send_mail
from django.core.validators import validate_email
from django.http import FileResponse, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone

from approval.approval_service import approve_content, reject_content, save_draft
from auth.auth_service import (
    authenticate_user,
    change_password,
    create_user,
    get_user_by_id,
    reset_password,
    send_password_reset_email,
)
from core.models import EmailRecipient, PostComment, PostSchedule
from core.services.content_generation import generate_topic_ideas
from core.services.schedule_import import import_schedule_file
from core.tasks import generate_post_draft
from demo.demo_calendar import export_demo_calendar_excel
from users.onboarding import build_brand_voice, get_brand_profile, onboarding_payload_to_profile


def _current_user(request):
    user_id = request.session.get("user_id")
    return get_user_by_id(user_id) if user_id else None


def _require_user(request):
    user = _current_user(request)
    if user is None:
        messages.error(request, "Please sign in to continue.")
        return None
    return user


def _require_profile(request, user):
    profile = get_brand_profile(user.id)
    if profile is None:
        messages.info(request, "Complete onboarding to continue.")
        return None
    return profile


def home(request):
    """Public landing page."""
    return render(
        request,
        "core/home.html",
        {
            "hide_sidebar": True,
            "session_user": _current_user(request),
        },
    )


def signup_view(request):
    """Signup and immediately route to onboarding."""
    if request.method == "POST":
        email = request.POST.get("email", "").strip()
        password = request.POST.get("password", "")
        confirm_password = request.POST.get("confirm_password", "")

        if password != confirm_password:
            messages.error(request, "Passwords do not match.")
            return render(request, "core/signup.html", {"hide_sidebar": True})

        try:
            user = create_user(email=email, password=password)
        except Exception as exc:
            messages.error(request, str(exc))
            return render(request, "core/signup.html", {"hide_sidebar": True})

        request.session["user_id"] = user.id
        request.session["user_email"] = user.email
        messages.success(request, "Signup successful. Complete onboarding next.")
        return redirect("onboarding")

    return render(request, "core/signup.html", {"hide_sidebar": True})


def login_view(request):
    """Login and route first-time users to onboarding."""
    if request.method == "POST":
        email = request.POST.get("email", "").strip()
        password = request.POST.get("password", "")
        user = authenticate_user(email=email, password=password)
        if user is None:
            messages.error(request, "Invalid email or password.")
            return render(request, "core/login.html", {"hide_sidebar": True})

        request.session["user_id"] = user.id
        request.session["user_email"] = user.email
        messages.success(request, "Welcome back.")
        return redirect("dashboard" if get_brand_profile(user.id) else "onboarding")

    return render(request, "core/login.html", {"hide_sidebar": True})


def forgot_password_view(request):
    """Send a password reset link to the user's email."""
    if request.method == "POST":
        email = request.POST.get("email", "").strip()
        try:
            reset_url = request.build_absolute_uri("/reset-password/")
            send_password_reset_email(email, reset_url)
            messages.success(request, "If the email exists, a reset link has been sent.")
            return redirect("login")
        except Exception as exc:
            messages.error(request, str(exc))
    return render(request, "core/forgot_password.html", {"hide_sidebar": True})


def reset_password_view(request):
    """Complete password reset using a token."""
    if request.method == "POST":
        email = request.POST.get("email", "").strip()
        token = request.POST.get("token", "").strip()
        new_password = request.POST.get("new_password", "")
        confirm_password = request.POST.get("confirm_password", "")
        if new_password != confirm_password:
            messages.error(request, "Passwords do not match.")
            return render(request, "core/reset_password.html", {"hide_sidebar": True, "email": email, "token": token})
        try:
            reset_password(email=email, token=token, new_password=new_password)
            messages.success(request, "Password reset successfully. Please log in.")
            return redirect("login")
        except Exception as exc:
            messages.error(request, str(exc))
    return render(
        request,
        "core/reset_password.html",
        {
            "hide_sidebar": True,
            "email": request.GET.get("email", ""),
            "token": request.GET.get("token", ""),
        },
    )


def logout_view(request):
    """Clear the session."""
    request.session.flush()
    messages.success(request, "You have been logged out.")
    return redirect("home")


def onboarding_view(request):
    """Capture brand details immediately after signup."""
    user = _require_user(request)
    if user is None:
        return redirect("login")

    profile = get_brand_profile(user.id)
    if request.method == "POST":
        payload = {
            "brand_name": request.POST.get("brand_name", ""),
            "niche": request.POST.get("niche", ""),
            "target_audience": request.POST.get("target_audience", ""),
            "preferred_platforms": request.POST.getlist("preferred_platforms") or [
                item.strip() for item in request.POST.get("preferred_platforms", "").split(",") if item.strip()
            ],
            "writing_tone": request.POST.get("writing_tone", ""),
            "content_goals": request.POST.getlist("content_goals") or [
                item.strip() for item in request.POST.get("content_goals", "").split(",") if item.strip()
            ],
        }
        if not payload["preferred_platforms"]:
            payload["preferred_platforms"] = ["LinkedIn"]
        if not payload["content_goals"]:
            payload["content_goals"] = ["Build audience", "Generate leads"]
        onboarding_payload_to_profile(user.id, payload)
        messages.success(request, "Brand profile saved.")
        return redirect("dashboard")

    return render(
        request,
        "core/onboarding.html",
        {
            "hide_sidebar": True,
            "profile": profile,
            "session_user": user,
        },
    )


def dashboard(request):
    """Private dashboard scoped to the current user."""
    user = _require_user(request)
    if user is None:
        return redirect("login")

    profile = _require_profile(request, user)
    if profile is None:
        return redirect("onboarding")

    action = request.POST.get("action")
    if request.method == "POST" and action == "change_password":
        old_password = request.POST.get("old_password", "")
        new_password = request.POST.get("new_password", "")
        confirm_password = request.POST.get("confirm_password", "")
        if new_password != confirm_password:
            messages.error(request, "New passwords do not match.")
            return redirect("dashboard")
        try:
            change_password(user.id, old_password, new_password)
            messages.success(request, "Password changed successfully.")
        except Exception as exc:
            messages.error(request, str(exc))
        return redirect("dashboard")
    if request.method == "POST" and action == "add_custom_topic":
        title = request.POST.get("topic", "").strip()
        if not title:
            messages.error(request, "Topic title is required.")
            return redirect("dashboard")
        scheduled_date = request.POST.get("scheduled_date", "").strip()
        scheduled_time = request.POST.get("scheduled_time", "").strip()
        scheduled_dt = timezone.now() + timedelta(days=1)
        if scheduled_date:
            try:
                parsed_date = datetime.fromisoformat(scheduled_date)
                if scheduled_time:
                    hh, mm = [int(part) for part in scheduled_time.split(":", 1)]
                    parsed_date = parsed_date.replace(hour=hh, minute=mm, second=0, microsecond=0)
                scheduled_dt = timezone.make_aware(parsed_date) if timezone.is_naive(parsed_date) else parsed_date
            except ValueError:
                messages.error(request, "Invalid schedule date or time.")
                return redirect("dashboard")
        PostSchedule.objects.create(
            user_id=user.id,
            date=scheduled_dt,
            topic=title,
            tone=request.POST.get("tone") or "Professional",
            category=request.POST.get("audience") or "General",
            platform=request.POST.get("platform") or "LinkedIn",
            post_type=request.POST.get("post_type") or "post",
            priority="Medium",
            status="draft",
        )
        messages.success(request, "Custom topic added to your draft queue.")
        return redirect("dashboard")
    if request.method == "POST" and action == "update_brand_profile":
        payload = {
            "brand_name": request.POST.get("brand_name", ""),
            "niche": request.POST.get("niche", ""),
            "target_audience": request.POST.get("target_audience", ""),
            "preferred_platforms": request.POST.getlist("preferred_platforms") or [
                item.strip() for item in request.POST.get("preferred_platforms", "").split(",") if item.strip()
            ],
            "writing_tone": request.POST.get("writing_tone", ""),
            "content_goals": request.POST.getlist("content_goals") or [
                item.strip() for item in request.POST.get("content_goals", "").split(",") if item.strip()
            ],
        }
        if not payload["preferred_platforms"]:
            payload["preferred_platforms"] = ["LinkedIn"]
        if not payload["content_goals"]:
            payload["content_goals"] = ["Build audience", "Generate leads"]
        onboarding_payload_to_profile(user.id, payload)
        messages.success(request, "Brand profile updated.")
        return redirect("dashboard")

    posts = PostSchedule.objects.filter(user_id=user.id)
    context = {
        "total": posts.count(),
        "pending": posts.filter(status="pending").count(),
        "approved": posts.filter(status="approved").count(),
        "published": posts.filter(status="published").count(),
        "draft": posts.filter(status="draft").count(),
        "rejected": posts.filter(status="rejected").count(),
        "upcoming": posts.filter(status__in=["draft", "pending", "approved"]).order_by("date")[:8],
        "recent": posts.order_by("-updated_at")[:5],
        "profile": profile,
        "brand_voice": build_brand_voice(profile),
        "brand_profile": profile,
    }
    return render(request, "core/dashboard.html", context)


def generate_topics_view(request):
    """Generate user-specific topic ideas."""
    user = _require_user(request)
    if user is None:
        return redirect("login")

    profile = _require_profile(request, user)
    if profile is None:
        return redirect("onboarding")

    if request.method == "POST":
        query = request.POST.get("query", profile.niche or "content strategy")
        tone = request.POST.get("tone", profile.tone or "Professional")
        audience = request.POST.get("audience", profile.audience or "General audience")
        platform = request.POST.get("platform", (profile.platforms or ["LinkedIn"])[0])
        count_raw = request.POST.get("count", "4")
        try:
            count = max(1, min(8, int(count_raw)))
        except ValueError:
            count = 4
        generated, error = generate_topic_ideas(
            query,
            tone,
            audience,
            platform=platform,
            niche=profile.niche,
            goals=profile.goals,
            brand_voice=build_brand_voice(profile),
            count=count,
        )
        if error:
            return render(request, "core/partials/topic_results.html", {"topics": [], "error": error, "next_day": (timezone.localdate() + timedelta(days=1)).isoformat()})
        return render(request, "core/partials/topic_results.html", {"topics": generated, "next_day": (timezone.localdate() + timedelta(days=1)).isoformat()})

    posts = PostSchedule.objects.filter(user_id=user.id)
    return render(
        request,
        "core/topic_generator.html",
        {
            "draft_count": posts.filter(status="draft").count(),
            "pending_count": posts.filter(status="pending").count(),
            "approved_count": posts.filter(status="approved").count(),
            "published_count": posts.filter(status="published").count(),
            "profile": profile,
            "next_day": (timezone.localdate() + timedelta(days=1)).isoformat(),
        },
    )


def save_generated_topic(request):
    """Save a new topic to the current user's schedule."""
    user = _require_user(request)
    if user is None:
        return redirect("login")

    if request.method != "POST":
        return redirect("generate_topics")

    title = request.POST.get("title", "").strip()
    if not title:
        messages.error(request, "Topic title is required.")
        return redirect("generate_topics")

    scheduled_date = request.POST.get("scheduled_date", "").strip()
    scheduled_time = request.POST.get("scheduled_time", "").strip()
    scheduled_dt = timezone.now() + timedelta(days=1)
    if scheduled_date:
        try:
            parsed_date = datetime.fromisoformat(scheduled_date)
            if scheduled_time:
                hh, mm = [int(part) for part in scheduled_time.split(":", 1)]
                parsed_date = parsed_date.replace(hour=hh, minute=mm, second=0, microsecond=0)
            scheduled_dt = timezone.make_aware(parsed_date) if timezone.is_naive(parsed_date) else parsed_date
        except ValueError:
            messages.error(request, "Invalid schedule date or time.")
            return redirect("generate_topics")

    PostSchedule.objects.create(
        user_id=user.id,
        date=scheduled_dt,
        topic=title,
        tone=request.POST.get("tone") or "Professional",
        category=request.POST.get("audience") or "General",
        platform=request.POST.get("platform") or "LinkedIn",
        post_type=request.POST.get("post_type") or "post",
        priority="Medium",
        status="draft",
    )
    messages.success(request, "Topic added to your draft queue.")
    return redirect("dashboard")


def upload_csv(request):
    """Upload a schedule file for the current user."""
    user = _require_user(request)
    if user is None:
        return redirect("login")

    if request.method == "POST" and request.FILES.get("file"):
        file = request.FILES["file"]
        fs = FileSystemStorage()
        name = fs.save(file.name, file)
        try:
            created_count = import_schedule_file(fs.path(name), user_id=user.id)
            fs.delete(name)
            messages.success(request, f"Uploaded {created_count} scheduled topics.")
        except Exception as exc:
            messages.error(request, f"Upload failed: {exc}")
        return redirect("dashboard")
    return render(request, "core/upload.html")


def download_demo_excel(request):
    """Generate and stream a demo spreadsheet on demand."""
    path = export_demo_calendar_excel()
    return FileResponse(open(path, "rb"), as_attachment=True, filename="demo_calendar.xlsx")


def email_integration(request):
    """Manage email recipients."""
    user = _require_user(request)
    if user is None:
        return redirect("login")

    if request.method == "POST":
        raw_emails = request.POST.get("emails", "")
        name = request.POST.get("name", "").strip()
        emails = [
            email.strip().lower()
            for chunk in raw_emails.replace("\n", ",").split(",")
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
                defaults={"name": name, "is_active": True},
            )
            if not created and not recipient.is_active:
                recipient.is_active = True
                if name and not recipient.name:
                    recipient.name = name
                recipient.save(update_fields=["is_active", "name"])
            created_count += int(created)

        if created_count or emails:
            messages.success(request, f"Saved {len(emails) - len(invalid_emails)} active email recipient(s).")
        if invalid_emails:
            messages.error(request, "Invalid email(s): " + ", ".join(invalid_emails))
        return redirect("email_integration")

    recipients = EmailRecipient.objects.order_by("-is_active", "email")
    return render(
        request,
        "core/email_integration.html",
        {
            "recipients": recipients,
            "active_count": recipients.filter(is_active=True).count(),
            "fallback_email": settings.DEMO_RECIPIENT_EMAIL,
        },
    )


def toggle_email_recipient(request, recipient_id):
    """Toggle email recipient status."""
    user = _require_user(request)
    if user is None:
        return redirect("login")

    recipient = get_object_or_404(EmailRecipient, id=recipient_id)
    recipient.is_active = not recipient.is_active
    recipient.save(update_fields=["is_active"])
    messages.success(request, f"{'Enabled' if recipient.is_active else 'Disabled'} {recipient.email}.")
    return redirect("email_integration")


def review_dashboard(request):
    """Show the user's approval queue."""
    user = _require_user(request)
    if user is None:
        return redirect("login")

    pending = PostSchedule.objects.filter(user_id=user.id, status="pending").order_by("date")
    approved = PostSchedule.objects.filter(user_id=user.id, status="approved").order_by("date")
    rejected = PostSchedule.objects.filter(user_id=user.id, status="rejected").order_by("date")
    return render(request, "core/review_dashboard.html", {"pending": pending, "approved": approved, "rejected": rejected})


def approve_post(request, post_id):
    """Approve a post owned by the current user."""
    user = _require_user(request)
    if user is None:
        return redirect("login")

    post = get_object_or_404(PostSchedule, id=post_id, user_id=user.id)
    post.status = "approved"
    post.save(update_fields=["status", "updated_at"])
    return redirect("review_dashboard")


def reject_post(request, post_id):
    """Reject a post owned by the current user."""
    user = _require_user(request)
    if user is None:
        return redirect("login")

    post = get_object_or_404(PostSchedule, id=post_id, user_id=user.id)
    post.status = "rejected"
    post.save(update_fields=["status", "updated_at"])
    return redirect("review_dashboard")


def regenerate_post(request, post_id):
    """Regenerate content for the current user only."""
    user = _require_user(request)
    if user is None:
        return redirect("login")

    post = get_object_or_404(PostSchedule, id=post_id, user_id=user.id)
    generate_post_draft(post.id)
    messages.success(request, f"Regenerated content for '{post.topic}'.")
    return redirect("review_dashboard")


def history_view(request):
    """Show only the current user's published content."""
    user = _require_user(request)
    if user is None:
        return redirect("login")

    published = PostSchedule.objects.filter(user_id=user.id, status="published").order_by("-date")
    return render(request, "core/history.html", {"published": published})


def trigger_cron(request):
    """Generate drafts and send emails for the user's due content."""
    user = _require_user(request)
    if user is None:
        return redirect("login")

    today = timezone.localdate()
    tomorrow = today + timedelta(days=1)
    window_start = timezone.make_aware(datetime.combine(today, time.min))
    window_end = timezone.make_aware(datetime.combine(tomorrow + timedelta(days=1), time.min))

    due_posts = PostSchedule.objects.filter(
        user_id=user.id,
        status__in=["draft", "pending"],
        date__gte=window_start,
        date__lt=window_end,
    ).order_by("date")

    generated_count = 0
    for scheduled_post in due_posts:
        if scheduled_post.status == "draft":
            if generate_post_draft(scheduled_post.id):
                generated_count += 1

    approved = PostSchedule.objects.filter(user_id=user.id, status="approved", date__lte=timezone.now())
    published_count = approved.count()
    approved.update(status="published")

    if due_posts.exists():
        messages.success(
            request,
            f"Cron checked today and tomorrow: generated {generated_count} draft(s) and published {published_count} approved post(s).",
        )
    else:
        messages.info(request, f"No draft or pending posts found for today or tomorrow. Published {published_count} approved post(s) that were due.")
    return redirect("review_dashboard")


def post_detail(request, post_id):
    """Show a single post owned by the current user."""
    user = _require_user(request)
    if user is None:
        return redirect("login")

    post = get_object_or_404(PostSchedule, id=post_id, user_id=user.id)
    if request.method == "POST":
        content = request.POST.get("content", "").strip()
        if content:
            PostComment.objects.create(post=post, user=user, content=content)
            messages.success(request, "Comment added.")
        return redirect("post_detail", post_id=post.id)
    return render(request, "core/post_detail.html", {"post": post})


def mark_post_published(request, post_id):
    """Mark a post as published after manual posting and store the live link."""
    user = _require_user(request)
    if user is None:
        return redirect("login")

    post = get_object_or_404(PostSchedule, id=post_id, user_id=user.id)
    if request.method == "POST":
        published_link = request.POST.get("published_link", "").strip()
        if not published_link:
            messages.error(request, "Published link is required for verification.")
            return redirect("post_detail", post_id=post.id)
        if not (published_link.startswith("http://") or published_link.startswith("https://")):
            messages.error(request, "Please enter a valid live URL.")
            return redirect("post_detail", post_id=post.id)
        post.published_link = published_link
        post.status = "published"
        post.save(update_fields=["published_link", "status", "updated_at"])
        messages.success(request, "Post marked as published.")
    return redirect("post_detail", post_id=post.id)


def advanced_ai_action(request, post_id, tool):
    """Proxy advanced AI actions for a user-owned post."""
    user = _require_user(request)
    if user is None:
        return JsonResponse({"result": "Authentication required."}, status=401)

    post = get_object_or_404(PostSchedule, id=post_id, user_id=user.id)
    prompts = {
        "hashtag": f"Suggest 8 LinkedIn hashtags for this topic: {post.topic}",
        "hook": f"Write 5 stronger LinkedIn hooks for this post topic: {post.topic}",
        "rewrite": f"Rewrite this LinkedIn post in a sharper professional tone:\n\n{post.generated_content}",
    }
    from .services.ai_client import ask_ollama

    return JsonResponse({"result": ask_ollama(prompts.get(tool, prompts["rewrite"]))})
