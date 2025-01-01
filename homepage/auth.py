from django.contrib.auth import get_user_model
from django.conf import settings
from google.oauth2 import id_token
from google.auth.transport import requests
from django.core.exceptions import ValidationError
from google_auth_oauthlib.flow import Flow
from google.oauth2.credentials import Credentials
import json
import jwt
import os

User = get_user_model()

class GoogleOAuth2Backend:
    """Google OAuth2認証バックエンド"""

    def authenticate(self, request, token=None, **kwargs):
        if not token:
            return None

        try:
            # トークンのデコード
            decoded_token = jwt.decode(token, options={"verify_signature": False})
            print("Decoded token:", decoded_token)  # デバッグ用
            
            # ユーザー情報の取得
            google_id = decoded_token['sub']
            email = decoded_token['email']
            name = decoded_token.get('name', '')
            picture = decoded_token.get('picture', '')
            email_verified = decoded_token.get('email_verified', False)

            if not email_verified:
                raise ValidationError('Email not verified.')

            # ユーザーの取得または作成
            try:
                user = User.objects.get(google_id=google_id)
                # 既存ユーザーの情報更新
                user.email = email
                user.avatar_url = picture
                user.save()
            except User.DoesNotExist:
                # 新規ユーザーの作成
                username = f'google_{google_id}'
                user = User.objects.create(
                    username=username,
                    email=email,
                    google_id=google_id,
                    avatar_url=picture,
                    is_active=True
                )
                user.set_unusable_password()
                # 名前の設定
                if ' ' in name:
                    first_name, last_name = name.rsplit(' ', 1)
                    user.first_name = first_name
                    user.last_name = last_name
                else:
                    user.first_name = name
                user.save()

            return user

        except (ValueError, ValidationError, jwt.InvalidTokenError) as e:
            print(f"Authentication error: {str(e)}")  # デバッグ用
            return None

    def get_user(self, user_id):
        try:
            return User.objects.get(pk=user_id)
        except User.DoesNotExist:
            return None

def create_oauth_flow():
    # クライアントシークレットファイルのパスを絶対パスで指定
    client_secrets_file = os.path.join(settings.BASE_DIR, "client_secret.json")
    
    # スコープを指定
    scopes = [
        'https://www.googleapis.com/auth/youtube.upload',
        'https://www.googleapis.com/auth/youtube'
    ]
    
    # Flow オブジェクトを作成
    flow = Flow.from_client_secrets_file(
        client_secrets_file,
        scopes=scopes,
        redirect_uri='http://localhost:8000/oauth2callback'  # リダイレクトURIを修正
    )
    
    return flow
