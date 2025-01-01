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
import vertexai
from vertexai.generative_models import GenerativeModel, Part, SafetySetting

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
    try:
        video = Video.objects.get(id=video_id)
        video.status = 'uploading'
        video.save()

        # ユーザーのYouTube認証情報を取得
        credentials = get_youtube_credentials(video.user)

        # YouTube APIクライアントの構築
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

        # 動画ファイルのアップロード
        insert_request = youtube.videos().insert(
            part=','.join(body.keys()),
            body=body,
            media_body=MediaFileUpload(
                video.local_file.path,
                chunksize=-1,
                resumable=True
            )
        )

        # アップロードの実行
        response = None
        while response is None:
            status, response = insert_request.next_chunk()
            if status:
                logger.info(f'Uploaded {int(status.progress() * 100)}%')

        # アップロード成功時の処理
        video.youtube_id = response['id']
        video.youtube_url = f'https://www.youtube.com/watch?v={response["id"]}'
        video.status = 'completed'
        video.save()

        # 分析タスクをキューに追加
        VideoProcessingQueue.objects.create(
            video=video,
            task_type='analyze',
            priority=1
        )

    except Exception as e:
        logger.error(f'YouTube upload error: {str(e)}')
        if video:
            video.status = 'failed'
            video.error_message = str(e)
            video.save()

def analyze_video_with_gemini(video_id):
    """Vertex AI Geminiで動画を分析する"""
    try:
        video = Video.objects.get(id=video_id)
        video.status = 'analyzing'
        video.save()

        # Vertex AIの初期化
        vertexai.init(project=os.environ.get('GOOGLE_CLOUD_PROJECT'), location="asia-northeast1")
        
        # Geminiモデルの設定
        generation_config = {
            "max_output_tokens": 8192,
            "temperature": 1,
            "top_p": 0.95,
        }

        safety_settings = [
            SafetySetting(
                category=SafetySetting.HarmCategory.HARM_CATEGORY_HATE_SPEECH,
                threshold=SafetySetting.HarmBlockThreshold.OFF
            ),
            SafetySetting(
                category=SafetySetting.HarmCategory.HARM_CATEGORY_DANGEROUS_CONTENT,
                threshold=SafetySetting.HarmBlockThreshold.OFF
            ),
            SafetySetting(
                category=SafetySetting.HarmCategory.HARM_CATEGORY_SEXUALLY_EXPLICIT,
                threshold=SafetySetting.HarmBlockThreshold.OFF
            ),
            SafetySetting(
                category=SafetySetting.HarmCategory.HARM_CATEGORY_HARASSMENT,
                threshold=SafetySetting.HarmBlockThreshold.OFF
            ),
        ]

        model = GenerativeModel(
            "gemini-1.5-pro-002",
        )

        # YouTube Data APIで動画情報を取得
        credentials = get_youtube_credentials(video.user)
        youtube = build('youtube', 'v3', credentials=credentials)

        # 動画の詳細情報を取得
        video_response = youtube.videos().list(
            part='snippet,contentDetails',
            id=video.youtube_id
        ).execute()

        if not video_response['items']:
            raise Exception('Video not found on YouTube')

        video_data = video_response['items'][0]
        
        # Geminiによる分析
        prompt = f"""
        以下の動画を分析してください：
        タイトル: {video_data['snippet']['title']}
        説明: {video_data['snippet']['description']}
        URL: {video.youtube_url}

        以下の観点で分析してください：
        1. 動画の主要なトピックや要点
        2. 重要な時間帯とその内容
        3. 感情分析（ポジティブ/ネガティブ）
        4. 改善点や提案

        結果は以下のJSON形式で返してください：
        {
            "summary": "全体的な要約",
            "topics": ["トピック1", "トピック2", ...],
            "timestamps": [
                {"time": "秒数", "content": "内容", "sentiment": "感情スコア"}
            ],
            "suggestions": ["提案1", "提案2", ...]
        }
        """

        # 分析の実行（ストリーミング）
        responses = model.generate_content(
            [prompt],
            generation_config=generation_config,
            safety_settings=safety_settings,
            stream=True,
        )

        # レスポンスの結合
        full_response = ""
        for response in responses:
            full_response += response.text

        # JSON解析
        analysis_data = json.loads(full_response)

        # 分析結果の保存
        video.analysis_summary = analysis_data['summary']
        video.analysis_data = analysis_data
        video.status = 'completed'
        video.save()

        # タイムスタンプ付きレビューの作成
        for timestamp_data in analysis_data['timestamps']:
            TimeStampedReview.objects.create(
                video=video,
                timestamp=int(timestamp_data['time']),
                content=timestamp_data['content'],
                sentiment=float(timestamp_data['sentiment'])
            )

    except Exception as e:
        logger.error(f'Gemini analysis error: {str(e)}')
        if video:
            video.status = 'failed'
            video.error_message = str(e)
            video.save()

def process_video_queue():
    """動画処理キューを処理する"""
    # 処理待ちのタスクを取得
    tasks = VideoProcessingQueue.objects.filter(
        attempts__lt=models.F('max_attempts')
    ).select_related('video')

    for task in tasks:
        try:
            # 最終試行時刻を更新
            task.last_attempt = timezone.now()
            task.attempts += 1
            task.save()

            # タスクタイプに応じた処理を実行
            if task.task_type == 'upload':
                upload_to_youtube(task.video.id)
            elif task.task_type == 'analyze':
                analyze_video_with_gemini(task.video.id)

            # 成功したタスクを削除
            task.delete()

        except Exception as e:
            logger.error(f'Task processing error: {str(e)}')
            # エラー時はタスクを保持（リトライ用）
            task.save()
