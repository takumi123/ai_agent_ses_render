import os
import json
import logging
from datetime import datetime
from django.conf import settings
from django.utils import timezone
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload

from .models import User, Video, TimeStampedReview, VideoProcessingQueue

logger = logging.getLogger(__name__)

def get_youtube_credentials(user):
    """ユーザーのYouTube認証情報を取得する"""
    # ユーザーモデルに認証情報を保存するフィールドを追加する必要があります
    if not user.youtube_credentials:
        raise Exception('YouTube認証が必要です')
    return Credentials.from_authorized_user_info(
        json.loads(user.youtube_credentials),
        ['https://www.googleapis.com/auth/youtube.upload']
    )

def upload_to_youtube(video_id):
    """動画をYouTubeにアップロードする"""
    video = None
    try:
        logger.info(f'Starting YouTube upload process for video ID: {video_id}')
        
        # 動画情報の取得
        try:
            video = Video.objects.get(id=video_id)
            logger.info(f'Found video: {video.title}')
        except Video.DoesNotExist:
            raise Exception('動画が見つかりません')
        
        # ファイルの存在確認
        if not os.path.exists(video.local_file.path):
            raise Exception('動画ファイルが見つかりません')

        # ファイルサイズの確認
        file_size = os.path.getsize(video.local_file.path)
        if file_size == 0:
            raise Exception('動画ファイルが空です')
        logger.info(f'Video file size: {file_size} bytes')

        # ステータスを更新
        video.status = 'uploading'
        video.save()
        logger.info('Updated status to uploading')

        # ユーザーのYouTube認証情報を取得
        try:
            logger.info('Getting YouTube credentials')
            credentials = get_youtube_credentials(video.user)
            logger.info('Successfully got YouTube credentials')
        except Exception as e:
            raise Exception(f'YouTube認証エラー: {str(e)}')

        try:
            # YouTube APIクライアントの構築
            logger.info('Building YouTube API client')
            youtube = build('youtube', 'v3', credentials=credentials)

            # 動画のメタデータを設定
            body = {
                'snippet': {
                    'title': video.title,
                    'description': video.description,
                    'tags': ['AI分析対象']
                },
                'status': {
                    'privacyStatus': 'unlisted'
                }
            }
            logger.info('Prepared video metadata')

            # 動画ファイルのアップロード準備
            logger.info(f'Preparing to upload file: {video.local_file.path}')
            media = MediaFileUpload(
                video.local_file.path,
                chunksize=-1,
                resumable=True
            )

            # アップロードリクエストの作成
            insert_request = youtube.videos().insert(
                part=','.join(body.keys()),
                body=body,
                media_body=media
            )
            logger.info('Created upload request')

            # アップロードの実行
            response = None
            last_progress = 0
            while response is None:
                try:
                    status, response = insert_request.next_chunk()
                    if status:
                        progress = int(status.progress() * 100)
                        if progress > last_progress:
                            logger.info(f'Upload progress: {progress}%')
                            last_progress = progress
                except Exception as e:
                    raise Exception(f'アップロード中にエラーが発生しました: {str(e)}')

            if not response:
                raise Exception('アップロードに失敗しました')

            # アップロード成功時の処理
            logger.info('Upload completed successfully')
            video.youtube_id = response['id']
            video.youtube_url = f'https://www.youtube.com/watch?v={response["id"]}'
            video.status = 'completed'
            video.save()
            logger.info(f'Video available at: {video.youtube_url}')

        except Exception as e:
            raise Exception(f'YouTube API エラー: {str(e)}')

    except Exception as e:
        error_msg = str(e)
        logger.error(f'Upload error: {error_msg}', exc_info=True)
        if video:
            video.status = 'failed'
            video.error_message = error_msg
            video.save()
            logger.info(f'Updated video status to failed: {error_msg}')
        raise  # エラーを再度発生させて呼び出し元で処理できるようにする

def process_video_queue():
    """動画処理キューを処理する"""
    logger.info("Starting video queue processing...")
    
    try:
        # 処理待ちのタスクを取得
        tasks = VideoProcessingQueue.objects.filter(
            attempts__lt=3  # max_attemptsを直接指定
        ).select_related('video')
        
        logger.info(f"Found {tasks.count()} tasks to process")

        for task in tasks:
            try:
                logger.info(f"Processing task {task.id} for video {task.video.id} (type: {task.task_type})")
                
                # 最終試行時刻を更新
                task.last_attempt = timezone.now()
                task.attempts += 1
                task.save()

                # タスクタイプに応じた処理を実行
                if task.task_type == 'upload':
                    logger.info(f"Starting YouTube upload for video {task.video.id}")
                    upload_to_youtube(task.video.id)
                    logger.info(f"YouTube upload completed for video {task.video.id}")

                # 成功したタスクを削除
                task.delete()
                logger.info(f"Task {task.id} completed successfully")

            except Exception as e:
                logger.error(f'Task processing error for task {task.id}: {str(e)}')
                # エラー時はタスクを保持（リトライ用）
                task.error_message = str(e)
                task.save()
                
    except Exception as e:
        logger.error(f'Queue processing error: {str(e)}')
