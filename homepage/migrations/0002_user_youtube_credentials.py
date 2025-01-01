# Generated by Django 5.0.1 on 2025-01-01 13:19

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('homepage', '0001_initial'),
    ]

    operations = [
        migrations.AddField(
            model_name='user',
            name='youtube_credentials',
            field=models.TextField(blank=True, help_text='YouTube API認証情報（JSON形式）', null=True),
        ),
    ]