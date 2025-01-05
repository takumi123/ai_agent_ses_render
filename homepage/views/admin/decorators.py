from functools import wraps
from django.shortcuts import redirect
from django.contrib import messages

def admin_required(view_func):
    @wraps(view_func)
    def _wrapped_view(request, *args, **kwargs):
        if not request.user.is_authenticated:
            messages.error(request, 'ログインが必要です。')
            return redirect('login')
        if not request.user.is_staff:
            messages.error(request, '管理者権限が必要です。')
            return redirect('homepage:index')
        return view_func(request, *args, **kwargs)
    return _wrapped_view
