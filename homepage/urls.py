from django.urls import path
from django.contrib.auth.views import LogoutView
from . import views

app_name = 'homepage'

urlpatterns = [
    # 認証関連
    path('', views.index, name='index'),
    path('login/google/', views.google_login, name='google_login'),
    path('login/google/callback', views.google_callback, name='google_callback'),
    path('logout/', LogoutView.as_view(), name='logout'),
    path('youtube/auth/', views.youtube_auth, name='youtube_auth'),
    path('youtube/callback', views.youtube_oauth2callback, name='youtube_oauth2callback'),

    # 動画関連
    path('videos/', views.video_list, name='video_list'),
    path('videos/upload/', views.video_upload, name='video_upload'),
    path('videos/<int:video_id>/', views.video_detail, name='video_detail'),
    path('videos/<int:video_id>/status/', views.video_status, name='video_status'),
    path('videos/<int:video_id>/reviews/', views.review_list, name='review_list'),

    # 管理者用
    path('users/', views.user_list, name='user_list'),

    # OAuth関連
    path('oauth2callback', views.oauth2callback, name='oauth2callback'),
    path('authorize', views.authorize, name='authorize'),
]
