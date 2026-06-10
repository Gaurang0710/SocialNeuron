from django.urls import path
from . import views

urlpatterns = [
    path('', views.dashboard, name='dashboard'),
    path('topic-generator/', views.generate_topics_view, name='generate_topics'),
    path('topic-generator/save/', views.save_generated_topic, name='save_generated_topic'),
    path('excel-upload/', views.upload_csv, name='upload_csv'),
    path('email-integration/', views.email_integration, name='email_integration'),
    path('email-integration/<int:recipient_id>/toggle/', views.toggle_email_recipient, name='toggle_email_recipient'),
    path('review/', views.review_dashboard, name='review_dashboard'),
    path('review/<int:post_id>/approve/', views.approve_post, name='approve_post'),
    path('review/<int:post_id>/reject/', views.reject_post, name='reject_post'),
    path('review/<int:post_id>/regenerate/', views.regenerate_post, name='regenerate_post'),
    path('post/<int:post_id>/', views.post_detail, name='post_detail'),
    path('post/<int:post_id>/advanced-ai/<str:tool>/', views.advanced_ai_action, name='advanced_ai_action'),
    path('history/', views.history_view, name='history_view'),
    path('trigger-cron/', views.trigger_cron, name='trigger_cron'),
]
