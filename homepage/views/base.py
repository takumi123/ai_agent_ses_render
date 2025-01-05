import json
from django.shortcuts import render, redirect, get_object_or_404
from django.http import HttpResponse
from django.contrib.auth import login, logout
from django.contrib.auth.decorators import login_required, user_passes_test
from django.http import JsonResponse
from django.views.decorators.http import require_http_methods
from django.views.decorators.csrf import csrf_exempt
from django.core.files.storage import default_storage
from django.conf import settings
from django.urls import reverse
from django.views.decorators.csrf import csrf_exempt
import logging
from google.oauth2 import id_token
from google.auth.transport import requests

from ..models import User, Video, TimeStampedReview, VideoProcessingQueue

logger = logging.getLogger(__name__)
from ..auth import GoogleOAuth2Backend, create_oauth_flow

def index(request):
    """トップページ"""
    # ログイン済みの場合はvideo_listにリダイレクト
    if request.user.is_authenticated:
        return redirect('homepage:video_list')
        
    context = {
        'GOOGLE_OAUTH_CLIENT_ID': settings.GOOGLE_OAUTH_CLIENT_ID,
        'recent_videos': []
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
                return redirect('homepage:video_list')
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

        flow = create_oauth_flow('google')
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

        # 認証情報をJSONとして保存
        credentials_json = {
            'token': credentials.token,
            'refresh_token': credentials.refresh_token,
            'token_uri': credentials.token_uri,
            'client_id': credentials.client_id,
            'client_secret': credentials.client_secret,
            'scopes': credentials.scopes
        }
        user.youtube_credentials = json.dumps(credentials_json)
        user.save()

        # ユーザーをログイン状態にする
        login(request, user, backend='homepage.auth.GoogleOAuth2Backend')
        
        # 保存されたリダイレクト先があればそこに遷移
        next_url = request.session.get('next_url', '')
        if next_url:
            del request.session['next_url']
            return redirect(next_url)
        return redirect('homepage:video_list')

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

        if not video_file or not title:
            return JsonResponse({
                'success': False,
                'error': '動画ファイルとタイトルは必須です。'
            }, status=400)

        # YouTube認証チェック
        if not request.user.youtube_credentials:
            return JsonResponse({
                'success': False,
                'error': 'Google認証が必要です。トップページから再度ログインしてください。',
                'redirect_url': reverse('homepage:index')
            }, status=403)

        # 動画の保存
        video = Video.objects.create(
            user=request.user,
            title=title,
            description=description,
            local_file=video_file
        )

        # 直接YouTubeにアップロード
        from ..tasks import upload_to_youtube
        try:
            logger.info(f'Starting YouTube upload process for video {video.id}')
            logger.info(f'Video file path: {video.local_file.path}')
            logger.info(f'Video file size: {video.local_file.size} bytes')
            logger.info(f'User credentials: {request.user.youtube_credentials is not None}')

            upload_to_youtube(video.id)
            
            # 動画情報を再取得（アップロード後の状態を取得）
            video.refresh_from_db()
            
            if video.status == 'completed' and video.youtube_url:
                logger.info(f'Upload successful. YouTube URL: {video.youtube_url}')
                
                # サムネイルの更新
                if video.youtube_id:
                    video.thumbnail_url = f'https://img.youtube.com/vi/{video.youtube_id}/hqdefault.jpg'
                    video.save()
                    logger.info(f'Thumbnail URL updated: {video.thumbnail_url}')
                
                return JsonResponse({
                    'success': True,
                    'video_id': video.id,
                    'message': 'アップロードが完了しました',
                    'youtube_url': video.youtube_url,
                    'thumbnail_url': video.thumbnail_url
                })
            else:
                error_msg = video.error_message or 'アップロードに失敗しました'
                logger.error(f'Upload failed: {error_msg}')
                return JsonResponse({
                    'success': False,
                    'error': error_msg
                }, status=500)

        except Exception as e:
            logger.error(f'Upload error for video {video.id}: {str(e)}', exc_info=True)
            return JsonResponse({
                'success': False,
                'error': f'アップロードに失敗しました: {str(e)}'
            }, status=500)

    return render(request, 'homepage/video_upload.html')

@login_required
@csrf_exempt
def bulk_process_videos(request):
    """選択された動画の一括処理"""
    if not request.method == 'POST':
        return JsonResponse({'error': '不正なリクエストです。'}, status=400)

    video_ids = request.POST.getlist('video_ids[]')
    action = request.POST.get('action')

    if not video_ids:
        return JsonResponse({'error': '動画が選択されていません。'}, status=400)

    if action not in ['analyze', 'delete']:
        return JsonResponse({'error': '不正な操作です。'}, status=400)

    try:
        videos = Video.objects.filter(id__in=video_ids)
        
        # ユーザーの権限チェック
        if not request.user.is_admin:
            videos = videos.filter(user=request.user)
            if not videos.exists():
                return JsonResponse({'error': '権限がありません。'}, status=403)

        if action == 'analyze':
            # 分析タスクの作成
            for video in videos:
                if video.youtube_url:  # YouTube URLが存在する場合のみ分析を実行
                    VideoProcessingQueue.objects.get_or_create(
                        video=video,
                        task_type='analyze',
                        defaults={'priority': 1}
                    )
            return JsonResponse({
                'message': f'{videos.count()}件の動画の分析を開始しました。'
            })
        
        elif action == 'delete':
            # YouTubeからの削除とデータベースからの削除
            count = videos.count()
            failed_deletions = []

            # まずYouTubeから削除
            for video in videos:
                if video.youtube_id:  # YouTube IDがある場合のみ削除を試みる
                    try:
                        from ..tasks import delete_from_youtube
                        delete_from_youtube(video)
                    except Exception as e:
                        error_msg = f'YouTube動画の削除に失敗しました（ID: {video.id}）: {str(e)}'
                        logger.error(error_msg)
                        failed_deletions.append(error_msg)

            # データベースから削除
            videos.delete()

            # エラーメッセージの処理
            if failed_deletions:
                return JsonResponse({
                    'message': f'{count}件の動画をデータベースから削除しました。\n' +
                              'ただし、以下のYouTube動画の削除に失敗しました：\n' +
                              '\n'.join(failed_deletions)
                })
            return JsonResponse({
                'message': f'{count}件の動画を削除しました。'
            })

    except Exception as e:
        logger.error(f'Bulk process error: {str(e)}')
        return JsonResponse({
            'error': f'処理中にエラーが発生しました: {str(e)}'
        }, status=500)

def analyze_unprocessed_videos(request):
    """未分析の動画を検出して分析を実行"""
    if not request.user.is_admin:
        return JsonResponse({'error': '権限がありません。'}, status=403)

    # 分析が未実行の動画を検索（analysis_summaryが空で、youtube_urlが存在する動画）
    unprocessed_videos = Video.objects.filter(
        analysis_summary='',
        youtube_url__isnull=False
    ).exclude(youtube_url='')

    # 各動画に対して分析タスクを作成
    for video in unprocessed_videos:
        VideoProcessingQueue.objects.get_or_create(
            video=video,
            task_type='analyze',
            defaults={'priority': 1}
        )

    return JsonResponse({
        'message': f'{unprocessed_videos.count()}件の動画の分析を開始しました。'
    })

@login_required
@require_http_methods(["POST"])
def analyze_with_gemini(request, video_id):
    """Geminiで動画を分析"""
    video = get_object_or_404(Video, id=video_id)
    if not request.user.is_admin and video.user != request.user:
        return JsonResponse({'error': '権限がありません。'}, status=403)

    # 分析タスクの作成
    if video.youtube_url:
        VideoProcessingQueue.objects.get_or_create(
            video=video,
            task_type='analyze',
            defaults={'priority': 1}
        )
        return JsonResponse({
            'message': '動画の分析を開始しました。'
        })
    return JsonResponse({
        'error': 'YouTube URLが見つかりません。'
    }, status=400)

@login_required
def video_detail(request, video_id):
    """動画詳細"""
    video = get_object_or_404(Video, id=video_id)
    # ログイン済みユーザーの場合のみ is_admin をチェック
    if not getattr(request.user, 'is_admin', False) and video.user != request.user:
        return JsonResponse({'error': '権限がありません。'}, status=403)

    reviews = video.reviews.all()
    
    # 分析サマリー内の時間表記をリンクに変換
    import re
    def convert_to_seconds(time_str):
        parts = time_str.split(':')
        if len(parts) == 2:  # MM:SS
            return int(parts[0]) * 60 + int(parts[1])
        elif len(parts) == 3:  # HH:MM:SS
            return int(parts[0]) * 3600 + int(parts[1]) * 60 + int(parts[2])
        return 0

    def replace_timestamp(match):
        time_str = match.group(0)
        seconds = convert_to_seconds(time_str)
        return f'<a href="javascript:void(0)" onclick="seekTo({seconds})" class="text-blue-600 hover:text-blue-800">{time_str}</a>'

    analysis_summary = video.analysis_summary
    if analysis_summary:
        pattern = r'\d{2}:\d{2}(?::\d{2})?'
        analysis_summary = re.sub(pattern, replace_timestamp, analysis_summary)

    return render(request, 'homepage/video_detail.html', {
        'video': video,
        'reviews': reviews,
        'analysis_summary': analysis_summary
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
@user_passes_test(lambda u: u.is_admin)
def update_video_thumbnails(request):
    """既存の動画のサムネイルURLを更新"""
    # YouTube IDがあり、サムネイルURLが設定されていない動画を取得
    videos = Video.objects.filter(
        youtube_id__isnull=False
    ).exclude(youtube_id='')

    updated_count = 0
    for video in videos:
        # サムネイルURLを設定
        thumbnail_url = f'https://img.youtube.com/vi/{video.youtube_id}/hqdefault.jpg'
        if video.thumbnail_url != thumbnail_url:
            video.thumbnail_url = thumbnail_url
            video.save()
            updated_count += 1

    return JsonResponse({
        'message': f'{updated_count}件の動画のサムネイルを更新しました。'
    })

def logout_view(request):
    """ログアウト処理"""
    logout(request)
    return redirect('homepage:index')

def authorize(request):
    """Google OAuth2認証の開始"""
    # ログイン後のリダイレクト先を保存
    next_url = request.GET.get('next', '')
    if next_url:
        request.session['next_url'] = next_url

    flow = create_oauth_flow('google')
    authorization_url, state = flow.authorization_url(
        access_type='offline',
        include_granted_scopes='true',
        prompt='consent'  # 毎回同意画面を表示
    )
    
    # 認証状態をセッションに保存
    request.session['oauth_state'] = state
    print(f"Starting OAuth flow. Authorization URL: {authorization_url}")  # デバッグ用
    
    return redirect(authorization_url)
