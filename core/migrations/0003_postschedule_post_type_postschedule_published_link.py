from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0002_initial'),
    ]

    operations = [
        migrations.AddField(
            model_name='postschedule',
            name='post_type',
            field=models.CharField(default='post', max_length=100),
        ),
        migrations.AddField(
            model_name='postschedule',
            name='published_link',
            field=models.URLField(blank=True, null=True),
        ),
    ]
