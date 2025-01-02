from django import template
import re

register = template.Library()

@register.filter(is_safe=True)
def timestamp_to_link(text, youtube_id):
    """テキスト内の時間表記（00:00形式）をYouTubeリンクに変換"""
    if not text or not youtube_id:
        return text

    def convert_to_seconds(time_str):
        """時間表記を秒数に変換"""
        parts = time_str.split(':')
        if len(parts) == 2:  # MM:SS
            return int(parts[0]) * 60 + int(parts[1])
        elif len(parts) == 3:  # HH:MM:SS
            return int(parts[0]) * 3600 + int(parts[1]) * 60 + int(parts[2])
        return 0

    def replace_match(match):
        time_str = match.group(0)
        seconds = convert_to_seconds(time_str)
        return f'<a href="https://www.youtube.com/watch?v={youtube_id}&t={seconds}s" target="_blank" rel="noopener" class="text-blue-600 hover:text-blue-800">{time_str}</a>'

    # 時間表記（00:00 or 00:00:00形式）を検出して置換
    pattern = r'\d{2}:\d{2}(?::\d{2})?'
    return re.sub(pattern, replace_match, text)
