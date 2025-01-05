from django.shortcuts import render
from django.db.models import Count
from ..admin import admin_required
from ...models import Video, User

@admin_required
def dashboard(request):
    """管理者ダッシュボード"""
    total_videos = Video.objects.count()
    total_users = User.objects.count()
    videos_by_status = Video.objects.values('status').annotate(count=Count('id'))
    
    context = {
        'total_videos': total_videos,
        'total_users': total_users,
        'videos_by_status': videos_by_status,
    }
    return render(request, 'homepage/admin/dashboard.html', context)
