"""
Creator Portal — Category Management API.

Migrated from betterbliss-auth/creator/api_categories.py.
"""

import re
import logging

from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.response import Response

from creator.models import Category
from creator.permissions import IsEducatorOrAdmin

logger = logging.getLogger(__name__)


def _serialize_category(c):
    return {
        'id': str(c.id),
        'name': c.name,
        'slug': c.slug,
        'description': c.description or '',
        'icon_url': c.icon_url or '',
        'sort_order': c.sort_order,
        'is_active': c.is_active,
    }


@api_view(['GET'])
@permission_classes([IsEducatorOrAdmin])
def category_list(request):
    """List all categories."""
    categories = Category.objects.filter(is_active=True).order_by('sort_order', 'name')
    return Response({
        'categories': [_serialize_category(c) for c in categories],
    })


@api_view(['POST'])
@permission_classes([IsEducatorOrAdmin])
def category_create(request):
    """Create a new category."""
    name = request.data.get('name', '').strip()
    if not name:
        return Response({'error': 'name is required'}, status=status.HTTP_400_BAD_REQUEST)

    slug = re.sub(r'[^a-z0-9\s-]', '', name.lower().strip())
    slug = re.sub(r'[\s_]+', '-', slug).strip('-')

    if Category.objects.filter(slug=slug).exists():
        return Response({'error': 'Category with this slug already exists'}, status=status.HTTP_409_CONFLICT)

    cat = Category(
        name=name,
        slug=slug,
        description=request.data.get('description', ''),
        sort_order=int(request.data.get('sort_order', 0)),
    )
    cat.save()

    logger.info(f'category.created id={cat.id}')
    return Response({'success': True, 'category': _serialize_category(cat)}, status=status.HTTP_201_CREATED)


@api_view(['PUT'])
@permission_classes([IsEducatorOrAdmin])
def category_update(request, category_id):
    """Update category."""
    try:
        cat = Category.objects.get(id=category_id)
    except Category.DoesNotExist:
        return Response({'error': 'Category not found'}, status=status.HTTP_404_NOT_FOUND)

    updatable = ['name', 'description', 'sort_order']
    updated = False
    for field in updatable:
        if field in request.data:
            setattr(cat, field, request.data[field])
            updated = True

    if not updated:
        return Response({'error': 'No fields to update'}, status=status.HTTP_400_BAD_REQUEST)

    cat.save()
    logger.info(f'category.updated id={category_id}')

    return Response({'success': True, 'category': _serialize_category(cat)})
