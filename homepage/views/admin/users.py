from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.core.paginator import Paginator
from django.db.models import Q
from . import admin_required
from ...models import User, Video

@admin_required
def user_list(request):
    """ユーザー一覧"""
    query = request.GET.get('q', '')
    users = User.objects.all().order_by('-date_joined')
    
    if query:
        users = users.filter(
            Q(username__icontains=query) |
            Q(email__icontains=query)
        )
    
    paginator = Paginator(users, 20)
    page = request.GET.get('page')
    users = paginator.get_page(page)
    
    return render(request, 'homepage/admin/users.html', {'users': users})

@admin_required
def user_toggle_admin(request, user_id):
    """ユーザーの管理者権限を切り替え"""
    if request.method != 'POST':
        return redirect('homepage:admin_users')
    
    user = get_object_or_404(User, id=user_id)
    if user == request.user:
        messages.error(request, '自分自身の権限は変更できません')
    else:
        user.is_admin = not user.is_admin
        user.save()
        messages.success(request, f'{user.username}の管理者権限を{"付与" if user.is_admin else "削除"}しました')
    
    return redirect('homepage:admin_users')

@admin_required
def user_delete(request, user_id):
    """ユーザーを削除"""
    if request.method != 'POST':
        return redirect('homepage:admin_users')
    
    user = get_object_or_404(User, id=user_id)
    if user == request.user:
        messages.error(request, '自分自身は削除できません')
    elif user.is_admin:
        messages.error(request, '管理者は削除できません')
    else:
        # ユーザーの動画を削除
        for video in user.videos.all():
            if video.youtube_id:
                try:
                    delete_from_youtube(video)
                except Exception as e:
                    messages.warning(request, f'YouTube動画の削除に失敗: {str(e)}')
        
        username = user.username
        user.delete()
        messages.success(request, f'ユーザー {username} を削除しました')
    
    return redirect('homepage:admin_users')

@admin_required
def user_videos(request, user_id):
    """ユーザーの動画一覧"""
    user = get_object_or_404(User, id=user_id)
    videos = user.videos.all().order_by('-created_at')
    
    paginator = Paginator(videos, 20)
    page = request.GET.get('page')
    videos = paginator.get_page(page)
    
    context = {
        'target_user': user,
        'videos': videos,
    }
    return render(request, 'homepage/admin/user_videos.html', context)
