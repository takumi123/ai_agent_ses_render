from django.shortcuts import render
from django.core.cache import cache

def index(request):
    # アクセス統計をRedisに記録
    stats = cache.get('hourly_stats', {})
    current_count = stats.get('access_count', 0)
    stats['access_count'] = current_count + 1
    cache.set('hourly_stats', stats, timeout=3600)
    
    return render(request, 'homepage/index.html', {})

def chat_room(request, room_name):
    return render(request, 'homepage/chat_room.html', {
        'room_name': room_name
    })
