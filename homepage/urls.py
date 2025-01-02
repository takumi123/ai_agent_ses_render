from django.urls import path
from . import views

app_name = 'homepage'

urlpatterns = [
    # 認証関連
    path('', views.index, name='index'),
    path('login/google/', views.google_login, name='google_login'),
    path('login/google/callback', views.google_callback, name='google_callback'),
    path('logout/', views.logout_view, name='logout'),
    # 動画関連
    path('videos/', views.video_list, name='video_list'),
    path('videos/upload/', views.video_upload, name='video_upload'),
    path('videos/<int:video_id>/', views.video_detail, name='video_detail'),
    path('videos/<int:video_id>/status/', views.video_status, name='video_status'),
    path('videos/<int:video_id>/reviews/', views.review_list, name='review_list'),
    path('videos/<int:video_id>/analyze-gemini/', views.analyze_with_gemini, name='analyze_with_gemini'),
    path('videos/bulk-process/', views.bulk_process_videos, name='bulk_process_videos'),

    # 管理者用
    path('users/', views.user_list, name='user_list'),
    path('videos/analyze-unprocessed/', views.analyze_unprocessed_videos, name='analyze_unprocessed_videos'),
    path('videos/update-thumbnails/', views.update_video_thumbnails, name='update_video_thumbnails'),

    # OAuth関連
    path('authorize', views.authorize, name='authorize'),
]
