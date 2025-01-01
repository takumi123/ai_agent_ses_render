from django.db import models
from django.contrib.auth.models import AbstractUser
from django.utils.translation import gettext_lazy as _

class User(AbstractUser):
    """カスタムユーザーモデル"""
    google_id = models.CharField(max_length=255, unique=True, null=True, blank=True)
    avatar_url = models.URLField(max_length=1000, null=True, blank=True)
    is_admin = models.BooleanField(default=False)
    youtube_credentials = models.TextField(null=True, blank=True, help_text='YouTube API認証情報（JSON形式）')

    class Meta:
        verbose_name = _('ユーザー')
        verbose_name_plural = _('ユーザー')

class Video(models.Model):
    """動画モデル"""
    STATUS_CHOICES = [
        ('pending', '処理待ち'),
        ('uploading', 'アップロード中'),
        ('analyzing', '分析中'),
        ('completed', '完了'),
        ('failed', '失敗'),
    ]

    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='videos')
    title = models.CharField(max_length=255)
    description = models.TextField(blank=True)
    youtube_id = models.CharField(max_length=20, unique=True, null=True, blank=True)
    youtube_url = models.URLField(max_length=1000, null=True, blank=True)
    local_file = models.FileField(upload_to='videos/', null=True, blank=True)
    duration = models.IntegerField(null=True, blank=True)  # 秒単位
    thumbnail_url = models.URLField(max_length=1000, null=True, blank=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    error_message = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    # Gemini分析結果
    analysis_summary = models.TextField(blank=True)
    analysis_data = models.JSONField(default=dict, blank=True)

    class Meta:
        verbose_name = _('動画')
        verbose_name_plural = _('動画')
        ordering = ['-created_at']

class TimeStampedReview(models.Model):
    """タイムスタンプ付きレビューモデル"""
    video = models.ForeignKey(Video, on_delete=models.CASCADE, related_name='reviews')
    timestamp = models.IntegerField()  # 秒単位
    content = models.TextField()
    sentiment = models.FloatField(null=True, blank=True)  # 感情分析スコア
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = _('タイムスタンプ付きレビュー')
        verbose_name_plural = _('タイムスタンプ付きレビュー')
        ordering = ['timestamp']
        unique_together = ['video', 'timestamp']

class VideoProcessingQueue(models.Model):
    """動画処理キューモデル"""
    TASK_CHOICES = [
        ('upload', 'YouTubeアップロード'),
        ('analyze', 'Gemini分析'),
    ]

    video = models.ForeignKey(Video, on_delete=models.CASCADE, related_name='processing_tasks')
    task_type = models.CharField(max_length=20, choices=TASK_CHOICES)
    priority = models.IntegerField(default=0)
    attempts = models.IntegerField(default=0)
    max_attempts = models.IntegerField(default=3)
    last_attempt = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = _('動画処理キュー')
        verbose_name_plural = _('動画処理キュー')
        ordering = ['-priority', 'created_at']
