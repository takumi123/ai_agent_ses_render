from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.http import JsonResponse
from ..admin import admin_required
from homepage.models import Video

@admin_required
def video_list(request):
    videos = Video.objects.all().order_by('-created_at')
    return render(request, 'homepage/admin/video_list.html', {'videos': videos})

@admin_required
def video_upload(request):
    if request.method == 'POST':
        # 実装は後で追加
        return redirect('homepage:admin_video_list')
    return render(request, 'homepage/admin/video_upload.html')

@admin_required
def video_delete(request, video_id):
    video = get_object_or_404(Video, id=video_id)
    video.delete()
    messages.success(request, '動画を削除しました。')
    return redirect('homepage:admin_video_list')

@admin_required
def video_analyze(request, video_id):
    video = get_object_or_404(Video, id=video_id)
    # 分析処理は後で実装
    return JsonResponse({'status': 'success'})
