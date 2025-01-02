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
from google.oauth2 import id_token
from google.auth.transport import requests

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

def google_login(request):
    """Googleログイン"""
    if request.method == 'POST':
        credential = request.POST.get('credential')
        print("Received credential:", credential)  # デバッグ用
        
        # ログイン後のリダイレクト先を保存
        next_url = request.GET.get('next', '')
        if next_url:
            request.session['next_url'] = next_url
        
        if not credential:
            print("No credential found in request")  # デバッグ用
            return redirect('homepage:index')
        
        try:
            backend = GoogleOAuth2Backend()
            user = backend.authenticate(request, token=credential)
            if user:
                login(request, user, backend='homepage.auth.GoogleOAuth2Backend')
                # 保存されたリダイレクト先があればそこに遷移
                next_url = request.session.get('next_url', '')
                if next_url:
                    del request.session['next_url']
                    return redirect(next_url)
                return redirect('homepage:video_upload')
            else:
                print("Authentication failed: User not created/found")  # デバッグ用
                return redirect('homepage:index')
        except Exception as e:
            print(f"Authentication error: {str(e)}")  # デバッグ用
            return redirect('homepage:index')
    
    return redirect('homepage:index')

def google_callback(request):
    """Googleログインコールバック"""
    try:
        # stateの検証
        state = request.GET.get('state')
        stored_state = request.session.get('oauth_state')
        if not state or state != stored_state:
            raise ValueError('State mismatch')

        flow = create_oauth_flow()
        flow.fetch_token(authorization_response=request.build_absolute_uri())
        credentials = flow.credentials

        # IDトークンを取得してユーザー情報を検証
        id_info = id_token.verify_oauth2_token(
            credentials.id_token,
            requests.Request(),
            settings.GOOGLE_OAUTH_CLIENT_ID
        )

        # ユーザー情報を取得
        google_id = id_info['sub']
        email = id_info['email']
        name = id_info.get('name', '')
        picture = id_info.get('picture', '')

        # ユーザーを取得または作成
        try:
            user = User.objects.get(google_id=google_id)
            # 既存ユーザーの情報を更新
            user.email = email
            user.avatar_url = picture
            user.save()
        except User.DoesNotExist:
            # 新規ユーザーを作成
            username = f'google_{google_id}'
            user = User.objects.create(
                username=username,
                email=email,
                google_id=google_id,
                avatar_url=picture,
                is_active=True
            )
            user.set_unusable_password()
            if ' ' in name:
                first_name, last_name = name.rsplit(' ', 1)
                user.first_name = first_name
                user.last_name = last_name
            else:
                user.first_name = name
            user.save()

        # ユーザーをログイン状態にする
        login(request, user, backend='homepage.auth.GoogleOAuth2Backend')
        
        # 保存されたリダイレクト先があればそこに遷移
        next_url = request.session.get('next_url', '')
        if next_url:
            del request.session['next_url']
            return redirect(next_url)
        return redirect('homepage:video_upload')

    except Exception as e:
        print(f"Google callback error: {str(e)}")  # デバッグ用
        return redirect('homepage:index')

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
    """Google OAuth2認証の開始"""
    # ログイン後のリダイレクト先を保存
    next_url = request.GET.get('next', '')
    if next_url:
        request.session['next_url'] = next_url

    flow = create_oauth_flow()
    authorization_url, state = flow.authorization_url(
        access_type='offline',
        include_granted_scopes='true',
        prompt='consent'  # 毎回同意画面を表示
    )
    
    # 認証状態をセッションに保存
    request.session['oauth_state'] = state
    print(f"Starting OAuth flow. Authorization URL: {authorization_url}")  # デバッグ用
    
    return redirect(authorization_url)
