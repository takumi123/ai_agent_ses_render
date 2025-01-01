from django.core.cache import cache
from django.utils import timezone
from datetime import timedelta
import logging

logger = logging.getLogger(__name__)

def daily_cleanup():
    """毎日0時に実行される清掃タスク"""
    # 1週間以上経過したキャッシュを削除
    week_ago = timezone.now() - timedelta(days=7)
    cache.delete_many([
        key for key in cache.keys('*')
        if cache.get(key).get('timestamp', timezone.now()) < week_ago
    ])
    logger.info('Daily cleanup completed')

def hourly_task():
    """毎時0分に実行されるタスク"""
    # アクセス統計の集計など
    stats = cache.get('hourly_stats', {})
    # 統計情報をリセット
    cache.set('hourly_stats', {}, timeout=3600)
    logger.info(f'Hourly task completed. Stats: {stats}')
