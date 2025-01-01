import json
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth import login
from django.contrib.auth.decorators import login_required, user_passes_test
from django.http import JsonResponse
from django.views.decorators.http import require_http_methods
from django.core.files.storage import default_storage
from django.conf import settings
from django.urls import reverse
from django.views.decorators.csrf import csrf_exempt

from .models import User, Video, TimeStampedReview, VideoProcessingQueue
from .auth import GoogleOAuth2Backend, create_oauth_flow

def index(request):
    """トップページ"""
    context = {
        'GOOGLE_OAUTH_CLIENT_ID': settings.GOOGLE_OAUTH_CLIENT_ID,
        'recent_videos': Video.objects.filter(status='completed').order_by('-created_at')[:6] if request.user.is_authenticated else []
    }
    print("GOOGLE_OAUTH_CLIENT_ID:", context['GOOGLE_OAUTH_CLIENT_ID'])  # デバッグ用
    return render(request, 'homepage/index.html', context)

@csrf_exempt
def google_login(request):
    """Googleログイン"""
    if request.method == 'POST':
        token = request.POST.get('credential')
        print("Received token:", token)  # デバッグ用
        if token:
            backend = GoogleOAuth2Backend()
            user = backend.authenticate(request, token=token)
            if user:
                login(request, user, backend='homepage.auth.GoogleOAuth2Backend')
                return JsonResponse({'success': True})
            else:
                print("Authentication failed")  # デバッグ用
    return JsonResponse({'success': False}, status=400)

def google_callback(request):
    """Googleログインコールバック"""
    code = request.GET.get('code')
    if code:
        flow = create_oauth_flow()
        flow.fetch_token(code=code)
        credentials = flow.credentials

        # 認証情報をセッションに保存
        request.session['credentials'] = {
            'token': credentials.token,
            'refresh_token': credentials.refresh_token,
            'token_uri': credentials.token_uri,
            'client_id': credentials.client_id,
            'client_secret': credentials.client_secret,
            'scopes': credentials.scopes
        }

        return redirect('homepage:index')
    return JsonResponse({'error': 'Authorization code not found.'}, status=400)

@login_required
def video_list(request):
    """動画一覧"""
    videos = Video.objects.all()
    if not request.user.is_admin:
        videos = videos.filter(user=request.user)
    return render(request, 'homepage/video_list.html', {'videos': videos})

@login_required
def video_upload(request):
    """動画アップロード"""
    if request.method == 'POST':
        video_file = request.FILES.get('video')
        title = request.POST.get('title')
        description = request.POST.get('description')
        user_id = request.POST.get('user_id')  # 管理者用

        if not video_file or not title:
            return JsonResponse({
                'success': False,
                'error': '動画ファイルとタイトルは必須です。'
            }, status=400)

        # アップロード対象のユーザーを決定
        target_user = request.user
        if request.user.is_admin and user_id:
            target_user = get_object_or_404(User, id=user_id)

        # YouTube認証チェック
        if not target_user.youtube_credentials:
            return JsonResponse({
                'success': False,
                'error': 'YouTube認証が必要です',
                'redirect_url': reverse('homepage:youtube_auth')
            }, status=403)

        # 動画の保存
        video = Video.objects.create(
            user=target_user,
            title=title,
            description=description,
            local_file=video_file
        )

        # アップロードタスクをキューに追加
        VideoProcessingQueue.objects.create(
            video=video,
            task_type='upload'
        )

        return JsonResponse({
            'success': True,
            'video_id': video.id
        })

    return render(request, 'homepage/video_upload.html')

@login_required
def video_detail(request, video_id):
    """動画詳細"""
    video = get_object_or_404(Video, id=video_id)
    if not request.user.is_admin and video.user != request.user:
        return JsonResponse({'error': '権限がありません。'}, status=403)

    reviews = video.reviews.all()
    return render(request, 'homepage/video_detail.html', {
        'video': video,
        'reviews': reviews
    })

@login_required
@user_passes_test(lambda u: u.is_admin)
def user_list(request):
    """ユーザー一覧（管理者用）"""
    users = User.objects.all()
    return render(request, 'homepage/user_list.html', {'users': users})

@login_required
def video_status(request, video_id):
    """動画の処理状態を取得"""
    video = get_object_or_404(Video, id=video_id)
    if not request.user.is_admin and video.user != request.user:
        return JsonResponse({'error': '権限がありません。'}, status=403)

    return JsonResponse({
        'status': video.status,
        'error_message': video.error_message,
        'youtube_url': video.youtube_url,
        'analysis_summary': video.analysis_summary
    })

@login_required
def review_list(request, video_id):
    """タイムスタンプ付きレビュー一覧を取得"""
    video = get_object_or_404(Video, id=video_id)
    if not request.user.is_admin and video.user != request.user:
        return JsonResponse({'error': '権限がありません。'}, status=403)

    reviews = video.reviews.all()
    return JsonResponse({
        'reviews': [
            {
                'timestamp': review.timestamp,
                'content': review.content,
                'sentiment': review.sentiment
            }
            for review in reviews
        ]
    })

@login_required
def youtube_auth(request):
    """YouTube認証開始"""
    print("Starting YouTube auth flow")  # デバッグ用
    flow = create_oauth_flow()
    authorization_url, state = flow.authorization_url(
        access_type='offline',
        include_granted_scopes='true'
    )
    print(f"Authorization URL: {authorization_url}")  # デバッグ用
    print(f"State: {state}")  # デバッグ用
    request.session['youtube_oauth_state'] = state
    return redirect(authorization_url)

@login_required
def youtube_oauth2callback(request):
    """YouTube認証コールバック"""
    try:
        flow = create_oauth_flow()
        flow.fetch_token(
            authorization_response=request.build_absolute_uri(),
            state=request.session.get('youtube_oauth_state')
        )
        credentials = flow.credentials
    except Exception as e:
        print(f"YouTube OAuth error: {str(e)}")
        return JsonResponse({'error': 'YouTube認証に失敗しました。'}, status=400)
    credentials_json = {
        'token': credentials.token,
        'refresh_token': credentials.refresh_token,
        'token_uri': credentials.token_uri,
        'client_id': credentials.client_id,
        'client_secret': credentials.client_secret,
        'scopes': credentials.scopes
    }

    # 認証情報を保存
    request.user.youtube_credentials = json.dumps(credentials_json)
    request.user.save()

    return redirect('homepage:video_upload')

def oauth2callback(request):
    flow = create_oauth_flow()
    
    # 現在のURLを取得
    current_url = request.build_absolute_uri()
    print(f"Current URL: {current_url}")  # デバッグ用
    
    try:
        # 認証コードを取得
        code = request.GET.get('code')
        if not code:
            return redirect('error')
            
        # 認証コードをトークンと交換
        flow.fetch_token(code=code)
        
        # 認証情報をセッションに保存
        credentials = flow.credentials
        request.session['credentials'] = {
            'token': credentials.token,
            'refresh_token': credentials.refresh_token,
            'token_uri': credentials.token_uri,
            'client_id': credentials.client_id,
            'client_secret': credentials.client_secret,
            'scopes': credentials.scopes
        }
        
        return redirect('homepage:video_upload')
    except Exception as e:
        print(f"OAuth error: {str(e)}")  # デバッグ用
        return redirect('error')

def authorize(request):
    flow = create_oauth_flow()
    authorization_url, state = flow.authorization_url(
        access_type='offline',
        include_granted_scopes='true'
    )
    request.session['state'] = state
    return redirect(authorization_url)
