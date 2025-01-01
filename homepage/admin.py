from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from django.utils.translation import gettext_lazy as _
from .models import User, Video, TimeStampedReview, VideoProcessingQueue

@admin.register(User)
class CustomUserAdmin(UserAdmin):
    """カスタムユーザー管理"""
    list_display = ('email', 'username', 'is_admin', 'is_staff', 'is_active', 'date_joined', 'last_login')
    list_filter = ('is_admin', 'is_staff', 'is_active')
    search_fields = ('email', 'username')
    ordering = ('-date_joined',)
    fieldsets = (
        (None, {'fields': ('email', 'username', 'password')}),
        (_('個人情報'), {'fields': ('first_name', 'last_name', 'google_id', 'avatar_url')}),
        (_('権限'), {'fields': ('is_active', 'is_staff', 'is_admin', 'is_superuser', 'groups', 'user_permissions')}),
        (_('重要な日付'), {'fields': ('last_login', 'date_joined')}),
    )
    add_fieldsets = (
        (None, {
            'classes': ('wide',),
            'fields': ('email', 'username', 'password1', 'password2'),
        }),
    )

@admin.register(Video)
class VideoAdmin(admin.ModelAdmin):
    """動画管理"""
    list_display = ('title', 'user', 'status', 'youtube_url', 'created_at')
    list_filter = ('status', 'created_at')
    search_fields = ('title', 'description', 'user__email')
    ordering = ('-created_at',)
    readonly_fields = ('youtube_id', 'youtube_url', 'analysis_summary', 'analysis_data')
    fieldsets = (
        (None, {
            'fields': ('user', 'title', 'description', 'local_file')
        }),
        (_('YouTube情報'), {
            'fields': ('youtube_id', 'youtube_url', 'thumbnail_url')
        }),
        (_('状態'), {
            'fields': ('status', 'error_message')
        }),
        (_('分析結果'), {
            'fields': ('analysis_summary', 'analysis_data')
        }),
    )

@admin.register(TimeStampedReview)
class TimeStampedReviewAdmin(admin.ModelAdmin):
    """タイムスタンプ付きレビュー管理"""
    list_display = ('video', 'timestamp', 'sentiment', 'created_at')
    list_filter = ('created_at', 'video')
    search_fields = ('content', 'video__title')
    ordering = ('video', 'timestamp')

@admin.register(VideoProcessingQueue)
class VideoProcessingQueueAdmin(admin.ModelAdmin):
    """動画処理キュー管理"""
    list_display = ('video', 'task_type', 'priority', 'attempts', 'created_at', 'last_attempt')
    list_filter = ('task_type', 'created_at')
    search_fields = ('video__title',)
    ordering = ('-priority', 'created_at')
    readonly_fields = ('attempts', 'last_attempt')
