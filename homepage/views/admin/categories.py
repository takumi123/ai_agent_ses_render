from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.http import JsonResponse
from django.views.decorators.http import require_POST
from django.views.decorators.csrf import csrf_exempt
import json
from . import admin_required
from ...models import EvaluationCategory, EvaluationSubCategory

@admin_required
def category_list(request):
    """評価カテゴリ一覧"""
    categories = EvaluationCategory.objects.prefetch_related('subcategories').all().order_by('order')
    return render(request, 'homepage/admin/categories.html', {'categories': categories})

@admin_required
@require_POST
def category_add(request):
    """カテゴリを追加"""
    name = request.POST.get('name')
    order = EvaluationCategory.objects.count()  # 新しいカテゴリは最後に追加
    
    try:
        EvaluationCategory.objects.create(name=name, order=order)
        messages.success(request, 'カテゴリを追加しました')
    except Exception as e:
        messages.error(request, f'カテゴリの追加に失敗しました: {str(e)}')
    
    return redirect('homepage:admin_categories')

@admin_required
@require_POST
def category_edit(request, category_id):
    """カテゴリを編集"""
    category = get_object_or_404(EvaluationCategory, id=category_id)
    name = request.POST.get('name')
    
    try:
        category.name = name
        category.save()
        messages.success(request, 'カテゴリを更新しました')
    except Exception as e:
        messages.error(request, f'カテゴリの更新に失敗しました: {str(e)}')
    
    return redirect('homepage:admin_categories')

@require_POST
@admin_required
def category_delete(request, category_id):
    """カテゴリを削除"""
    category = get_object_or_404(EvaluationCategory, id=category_id)
    try:
        category.delete()
        messages.success(request, 'カテゴリを削除しました')
    except Exception as e:
        messages.error(request, f'カテゴリの削除に失敗しました: {str(e)}')
    
    return redirect('homepage:admin_categories')

@admin_required
@require_POST
def category_reorder(request):
    """カテゴリの並び順を更新"""
    try:
        data = json.loads(request.body)
        categories = data.get('categories', [])
        
        for item in categories:
            category = EvaluationCategory.objects.get(id=item['id'])
            category.order = item['order']
            category.save()
        
        return JsonResponse({'status': 'success'})
    except Exception as e:
        return JsonResponse({'status': 'error', 'message': str(e)}, status=400)

@admin_required
@require_POST
def subcategory_add(request):
    """サブカテゴリを追加"""
    category_id = request.POST.get('category_id')
    category = get_object_or_404(EvaluationCategory, id=category_id)
    name = request.POST.get('name')
    description = request.POST.get('description')
    order = category.subcategories.count()  # 新しいサブカテゴリは最後に追加
    
    try:
        EvaluationSubCategory.objects.create(
            category=category,
            name=name,
            description=description,
            order=order
        )
        messages.success(request, 'サブカテゴリを追加しました')
    except Exception as e:
        messages.error(request, f'サブカテゴリの追加に失敗しました: {str(e)}')
    
    return redirect('homepage:admin_categories')

@admin_required
@require_POST
def subcategory_edit(request, subcategory_id):
    """サブカテゴリを編集"""
    subcategory = get_object_or_404(EvaluationSubCategory, id=subcategory_id)
    name = request.POST.get('name')
    description = request.POST.get('description')
    
    try:
        subcategory.name = name
        subcategory.description = description
        subcategory.save()
        messages.success(request, 'サブカテゴリを更新しました')
    except Exception as e:
        messages.error(request, f'サブカテゴリの更新に失敗しました: {str(e)}')
    
    return redirect('homepage:admin_categories')

@admin_required
@require_POST
def subcategory_delete(request, subcategory_id):
    """サブカテゴリを削除"""
    subcategory = get_object_or_404(EvaluationSubCategory, id=subcategory_id)
    try:
        subcategory.delete()
        messages.success(request, 'サブカテゴリを削除しました')
    except Exception as e:
        messages.error(request, f'サブカテゴリの削除に失敗しました: {str(e)}')
    
    return redirect('homepage:admin_categories')

@admin_required
@require_POST
def subcategory_reorder(request):
    """サブカテゴリの並び順を更新"""
    try:
        data = json.loads(request.body)
        subcategories = data.get('subcategories', [])
        
        for item in subcategories:
            subcategory = EvaluationSubCategory.objects.get(id=item['id'])
            subcategory.order = item['order']
            subcategory.save()
        
        return JsonResponse({'status': 'success'})
    except Exception as e:
        return JsonResponse({'status': 'error', 'message': str(e)}, status=400)
