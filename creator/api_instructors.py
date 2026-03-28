"""
Creator Portal — Instructor Management API.

CRUD + soft delete for instructor profiles.
Migrated from betterbliss-auth/creator/api_instructors.py.
"""

import re
import logging

from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.response import Response

from creator.models import Expert
from creator.permissions import IsEducatorOrAdmin

logger = logging.getLogger(__name__)


def _generate_slug(name):
    slug = name.lower().strip()
    slug = re.sub(r'[^a-z0-9\s-]', '', slug)
    slug = re.sub(r'[\s_]+', '-', slug)
    return slug.strip('-')


def _serialize_instructor(e):
    return {
        'id': str(e.id),
        'name': e.name,
        'slug': e.slug,
        'title': e.title or '',
        'bio': e.bio or '',
        'fun_fact': getattr(e, 'fun_fact', None) or '',
        'specialties': e.specialties if hasattr(e, 'specialties') else [],
        'image_url': e.avatar_url if hasattr(e, 'avatar_url') else '',
        'is_featured': e.is_featured,
        'is_active': getattr(e, 'is_active', True),
        'created_at': e.created_at.isoformat() if hasattr(e, 'created_at') and e.created_at else None,
    }


# =============================================================================
# CRUD
# =============================================================================

@api_view(['GET'])
@permission_classes([IsEducatorOrAdmin])
def instructor_list(request):
    """List all instructors."""
    qs = Expert.objects.all()

    featured = request.GET.get('featured')
    if featured is not None:
        qs = qs.filter(is_featured=featured.lower() in ('true', '1'))

    search = request.GET.get('search')
    if search:
        qs = qs.filter(name__icontains=search)

    limit = min(int(request.GET.get('limit', 50)), 100)
    offset = int(request.GET.get('offset', 0))

    instructors = qs.order_by('-is_featured', 'name')[offset:offset + limit]

    serialized = [_serialize_instructor(e) for e in instructors]

    return Response({
        'instructors': serialized,
        'experts': serialized,  # Alias for frontend compat
        'total': len(instructors),
    })


@api_view(['GET'])
@permission_classes([IsEducatorOrAdmin])
def instructor_detail(request, instructor_id):
    """Get instructor by ID."""
    try:
        instructor = Expert.objects.get(id=instructor_id)
    except Expert.DoesNotExist:
        return Response({'error': 'Instructor not found'}, status=status.HTTP_404_NOT_FOUND)

    serialized = _serialize_instructor(instructor)
    return Response({'instructor': serialized, 'expert': serialized})


@api_view(['POST'])
@permission_classes([IsEducatorOrAdmin])
def instructor_create(request):
    """Create a new instructor."""
    name = request.data.get('name', '').strip()
    title = request.data.get('title', '').strip()

    if not name or not title:
        return Response({'error': 'name and title are required'}, status=status.HTTP_400_BAD_REQUEST)

    slug = _generate_slug(name)
    if Expert.objects.filter(slug=slug).exists():
        slug = f"{slug}-{str(Expert.objects.count())}"

    instructor = Expert(
        name=name,
        slug=slug,
        title=title,
        bio=request.data.get('bio', ''),
        is_featured=request.data.get('featured', False),
    )
    instructor.save()

    logger.info(f'instructor.created id={instructor.id}')
    return Response({
        'success': True,
        'instructor': _serialize_instructor(instructor),
    }, status=status.HTTP_201_CREATED)


@api_view(['PUT'])
@permission_classes([IsEducatorOrAdmin])
def instructor_update(request, instructor_id):
    """Update instructor profile."""
    try:
        instructor = Expert.objects.get(id=instructor_id)
    except Expert.DoesNotExist:
        return Response({'error': 'Instructor not found'}, status=status.HTTP_404_NOT_FOUND)

    updatable = ['name', 'title', 'bio', 'fun_fact']
    updated = False
    for field in updatable:
        if field in request.data:
            setattr(instructor, field, request.data[field])
            updated = True

    if 'featured' in request.data:
        instructor.is_featured = request.data['featured']
        updated = True

    if not updated:
        return Response({'error': 'No fields to update'}, status=status.HTTP_400_BAD_REQUEST)

    instructor.save()
    logger.info(f'instructor.updated id={instructor_id}')

    return Response({'success': True, 'instructor': _serialize_instructor(instructor)})


@api_view(['DELETE'])
@permission_classes([IsEducatorOrAdmin])
def instructor_deactivate(request, instructor_id):
    """Soft-delete (deactivate) instructor."""
    from django.db import connection
    try:
        Expert.objects.get(id=instructor_id)
    except Expert.DoesNotExist:
        return Response({'error': 'Instructor not found'}, status=status.HTTP_404_NOT_FOUND)

    with connection.cursor() as cursor:
        cursor.execute(
            "UPDATE experts SET status = 'inactive', updated_at = NOW() WHERE id = %s",
            [str(instructor_id)]
        )

    logger.info(f'instructor.deactivated id={instructor_id}')
    return Response({'success': True, 'message': 'Instructor deactivated'})
