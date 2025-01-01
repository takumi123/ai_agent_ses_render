from google_auth_oauthlib.flow import InstalledAppFlow
import json

# 必要なスコープを設定
SCOPES = [
    'https://www.googleapis.com/auth/youtube.upload',
    'https://www.googleapis.com/auth/youtube.readonly'
]

def get_credentials():
    # OAuth 2.0クライアント設定
    client_config = {
        "web": {
            "client_id": "1005781284114-14q4aeq135fuqb5jchqjgunjfq9ubd90.apps.googleusercontent.com",
            "project_id": "find-partner-443223",
            "auth_uri": "https://accounts.google.com/o/oauth2/auth",
            "token_uri": "https://oauth2.googleapis.com/token",
            "auth_provider_x509_cert_url": "https://www.googleapis.com/oauth2/v1/certs",
            "client_secret": "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",
            "redirect_uris": [
                "http://localhost:8000/login/google/callback",
                "https://mysite-wecj.onrender.com/login/google/callback"
            ]
        }
    }

    # 認証フローを実行
    flow = InstalledAppFlow.from_client_config(
        client_config,
        scopes=SCOPES
    )
    credentials = flow.run_local_server(port=8080)

    # 認証情報をJSON形式で出力
    credentials_json = {
        'token': credentials.token,
        'refresh_token': credentials.refresh_token,
        'token_uri': credentials.token_uri,
        'client_id': credentials.client_id,
        'client_secret': credentials.client_secret,
        'scopes': credentials.scopes
    }
    
    print("YOUTUBE_CREDENTIALS用の認証情報:")
    print(json.dumps(credentials_json))

if __name__ == '__main__':
    get_credentials()
