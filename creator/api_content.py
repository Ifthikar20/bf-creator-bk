"""
Creator Portal — Content Management API.

Full 6-step upload pipeline + list/detail/archive.
Migrated from betterbliss-auth/creator/api_content.py.
"""

import uuid
import re
import secrets
import logging
import boto3
from botocore.config import Config as BotoConfig

from django.conf import settings as django_settings
from django.db import connection as django_connection

from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.response import Response

from creator.models import Content, Category, Expert, ContentStatus
from creator.permissions import IsEducatorOrAdmin

logger = logging.getLogger(__name__)


# Whitelisted display flag columns for raw SQL updates
_ALLOWED_DISPLAY_FLAGS = frozenset({
    'show_on_home', 'show_on_explore', 'show_on_meditate', 'featured', 'trending',
})


def _safe_int(value, default=0, min_val=None, max_val=None):
    """Safely convert to int with bounds."""
    try:
        result = int(value)
        if min_val is not None:
            result = max(result, min_val)
        if max_val is not None:
            result = min(result, max_val)
        return result
    except (TypeError, ValueError):
        return default


def _check_content_ownership(content, user):
    """Verify the user owns this content or is admin/staff."""
    if getattr(user, 'role', None) == 'admin' or getattr(user, 'is_staff', False):
        return None
    submitted_by = getattr(content, 'submitted_by', None)
    if submitted_by is not None and submitted_by == user:
        return None
    logger.warning(f'DENIED content.modify resource={content.id} user={user.id}')
    return Response({
        'success': False,
        'error': {
            'code': 'FORBIDDEN',
            'message': 'You can only modify content you created.',
        }
    }, status=status.HTTP_403_FORBIDDEN)


# =============================================================================
# HELPERS
# =============================================================================

def _generate_short_id(length=8):
    return secrets.token_urlsafe(length)[:length]


def _generate_slug(title):
    slug = title.lower().strip()
    slug = re.sub(r'[^a-z0-9\s-]', '', slug)
    slug = re.sub(r'[\s_]+', '-', slug)
    slug = re.sub(r'-+', '-', slug)
    return slug.strip('-')


def _get_s3_client():
    return boto3.client(
        's3',
        region_name=getattr(django_settings, 'AWS_REGION', 'us-east-1'),
        config=BotoConfig(signature_version='s3v4'),
    )


def _serialize_content(c):
    return {
        'id': str(c.id),
        'title': c.title,
        'description': c.description or '',
        'content_type': c.content_type,
        'category_id': str(c.category_id) if c.category_id else None,
        'category_name': c.category.name if c.category else None,
        'instructor_id': str(c.expert_id) if c.expert_id else None,
        'instructor_name': c.expert.name if c.expert else None,
        'thumbnail_s3_key': c.thumbnail_s3_key or '',
        'media_s3_key': c.media_s3_key or '',
        'duration_seconds': c.duration_seconds,
        'is_premium': c.is_premium,
        'status': c.status,
        'tags': c.tags or '',
        'view_count': c.view_count,
        'series_id': str(c.series_id) if c.series_id else None,
        'episode_number': c.episode_number,
        'created_at': c.created_at.isoformat() if c.created_at else None,
        'updated_at': c.updated_at.isoformat() if c.updated_at else None,
    }


# =============================================================================
# STEP 1: CREATE DRAFT
# =============================================================================

@api_view(['POST'])
@permission_classes([IsEducatorOrAdmin])
def content_create_draft(request):
    """Create a minimal content draft."""
    title = request.data.get('title', '').strip()
    content_type = request.data.get('content_type', 'video')

    if not title:
        return Response({'error': 'title is required'}, status=status.HTTP_400_BAD_REQUEST)

    if content_type not in ('video', 'audio', 'article'):
        content_type = 'video'

    slug = _generate_slug(title)
    if Content.objects.filter(tags__icontains=slug).exists():
        slug = f"{slug}-{_generate_short_id(8)}"

    content = Content(
        title=title,
        content_type=content_type,
        status=ContentStatus.DRAFT,
        submitted_by=request.user,
    )
    content.save()

    logger.info(f'content.draft_created id={content.id}')

    return Response({
        'success': True,
        'content': _serialize_content(content),
    }, status=status.HTTP_201_CREATED)


# =============================================================================
# STEP 2: UPLOAD THUMBNAIL
# =============================================================================

@api_view(['POST'])
@permission_classes([IsEducatorOrAdmin])
def content_upload_thumbnail(request, content_id):
    """Get presigned URL for thumbnail upload to S3."""
    try:
        content = Content.objects.get(id=content_id)
    except Content.DoesNotExist:
        return Response({'error': 'Content not found'}, status=status.HTTP_404_NOT_FOUND)

    denied = _check_content_ownership(content, request.user)
    if denied:
        return denied

    s3_key = f"thumbnails/{content.id}.jpg"

    try:
        s3 = _get_s3_client()
        bucket = getattr(django_settings, 'VIDEO_BUCKET_NAME', 'betterbliss-videos-production')
        presigned_url = s3.generate_presigned_url(
            'put_object',
            Params={'Bucket': bucket, 'Key': s3_key},
            ExpiresIn=3600,
        )
    except Exception as e:
        logger.error(f's3.thumbnail_url failed id={content_id}: {e}')
        return Response({'error': 'Failed to generate upload URL'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    return Response({'upload_url': presigned_url, 's3_key': s3_key, 'expires_in': 3600})


@api_view(['POST'])
@permission_classes([IsEducatorOrAdmin])
def content_confirm_thumbnail(request, content_id):
    """Confirm thumbnail was uploaded to S3."""
    s3_key = request.data.get('s3_key', '')
    if not s3_key:
        return Response({'error': 's3_key is required'}, status=status.HTTP_400_BAD_REQUEST)

    try:
        content = Content.objects.get(id=content_id)
    except Content.DoesNotExist:
        return Response({'error': 'Content not found'}, status=status.HTTP_404_NOT_FOUND)

    denied = _check_content_ownership(content, request.user)
    if denied:
        return denied

    cdn_domain = getattr(django_settings, 'CLOUDFRONT_DOMAIN', 'd2f89dacgjld08.cloudfront.net')
    content.thumbnail_s3_key = s3_key
    with django_connection.cursor() as cursor:
        cursor.execute(
            "UPDATE content SET s3_key_thumbnail = %s, thumbnail_url = %s, updated_at = NOW() WHERE id = %s",
            [s3_key, f"https://{cdn_domain}/{s3_key}", str(content_id)]
        )

    logger.info(f'content.thumbnail_confirmed id={content_id}')
    return Response({'success': True, 'thumbnail_key': s3_key})


# =============================================================================
# STEP 3: UPLOAD MEDIA
# =============================================================================

@api_view(['POST'])
@permission_classes([IsEducatorOrAdmin])
def content_upload_media(request, content_id):
    """Get presigned URL for media (video/audio) upload."""
    try:
        content = Content.objects.get(id=content_id)
    except Content.DoesNotExist:
        return Response({'error': 'Content not found'}, status=status.HTTP_404_NOT_FOUND)

    denied = _check_content_ownership(content, request.user)
    if denied:
        return denied

    filename = request.data.get('filename', '')
    if not filename:
        return Response({'error': 'filename is required'}, status=status.HTTP_400_BAD_REQUEST)

    extension = filename.rsplit('.', 1)[-1].lower() if '.' in filename else ''
    allowed_video = ['mp4', 'mov', 'avi', 'mkv', 'webm', 'm4v']
    allowed_audio = ['mp3', 'wav', 'm4a', 'aac', 'ogg', 'flac']
    allowed = allowed_video if content.content_type == 'video' else allowed_audio

    if extension not in allowed:
        return Response(
            {'error': f'Invalid file type. Allowed: {", ".join(allowed)}'},
            status=status.HTTP_400_BAD_REQUEST,
        )

    s3_key = f"uploads/{content.id}.{extension}"
    content_type_map = {
        'mp4': 'video/mp4', 'mov': 'video/quicktime',
        'mp3': 'audio/mpeg', 'wav': 'audio/wav', 'm4a': 'audio/m4a',
    }

    try:
        s3 = _get_s3_client()
        bucket = getattr(django_settings, 'VIDEO_BUCKET_NAME', 'betterbliss-videos-production')
        presigned_url = s3.generate_presigned_url(
            'put_object',
            Params={
                'Bucket': bucket,
                'Key': s3_key,
                'ContentType': content_type_map.get(extension, 'application/octet-stream'),
            },
            ExpiresIn=3600,
        )
    except Exception as e:
        logger.error(f's3.media_url failed id={content_id}: {e}')
        return Response({'error': 'Failed to generate upload URL'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    return Response({
        'upload_url': presigned_url,
        's3_key': s3_key,
        'bucket': bucket,
        'expires_in': 3600,
    })


@api_view(['POST'])
@permission_classes([IsEducatorOrAdmin])
def content_confirm_media(request, content_id):
    """Confirm media was uploaded to S3."""
    s3_key = request.data.get('s3_key', '')
    duration_seconds = request.data.get('duration_seconds')

    if not s3_key:
        return Response({'error': 's3_key is required'}, status=status.HTTP_400_BAD_REQUEST)

    try:
        content = Content.objects.get(id=content_id)
    except Content.DoesNotExist:
        return Response({'error': 'Content not found'}, status=status.HTTP_404_NOT_FOUND)

    denied = _check_content_ownership(content, request.user)
    if denied:
        return denied

    if content.content_type == 'video':
        with django_connection.cursor() as cursor:
            cursor.execute(
                "UPDATE content SET s3_key_original = %s, duration_seconds = COALESCE(%s, duration_seconds), has_video = true, updated_at = NOW() WHERE id = %s",
                [s3_key, duration_seconds, str(content_id)]
            )
    else:
        with django_connection.cursor() as cursor:
            cursor.execute(
                "UPDATE content SET s3_key_audio = %s, duration_seconds = COALESCE(%s, duration_seconds), updated_at = NOW() WHERE id = %s",
                [s3_key, duration_seconds, str(content_id)]
            )

    content.media_s3_key = s3_key
    if duration_seconds:
        content.duration_seconds = int(duration_seconds)
    content.save()

    logger.info(f'content.media_confirmed id={content_id}')
    return Response({'success': True, 'media_key': s3_key})


# =============================================================================
# STEP 4: UPDATE METADATA
# =============================================================================

@api_view(['PUT'])
@permission_classes([IsEducatorOrAdmin])
def content_update(request, content_id):
    """Update content metadata."""
    try:
        content = Content.objects.get(id=content_id)
    except Content.DoesNotExist:
        return Response({'error': 'Content not found'}, status=status.HTTP_404_NOT_FOUND)

    denied = _check_content_ownership(content, request.user)
    if denied:
        return denied

    field_map = {
        'title': 'title',
        'description': 'description',
        'is_premium': 'is_premium',
        'tags': 'tags',
        'duration_seconds': 'duration_seconds',
        'episode_number': 'episode_number',
    }

    updated = False
    for api_field, model_field in field_map.items():
        if api_field in request.data:
            setattr(content, model_field, request.data[api_field])
            updated = True

    if 'expert_id' in request.data:
        val = request.data['expert_id']
        content.expert_id = val if val else None
        updated = True

    if 'category_id' in request.data:
        val = request.data['category_id']
        content.category_id = val if val else None
        updated = True

    if 'series_id' in request.data:
        val = request.data['series_id']
        content.series_id = val if val else None
        updated = True

    # Display page flags (raw SQL for unmapped columns)
    display_flags = {}
    for flag in _ALLOWED_DISPLAY_FLAGS:
        if flag in request.data:
            display_flags[flag] = request.data[flag]

    if display_flags:
        sets = ', '.join(f"{k} = %s" for k in display_flags)
        vals = list(display_flags.values()) + [str(content_id)]
        with django_connection.cursor() as cursor:
            cursor.execute(f"UPDATE content SET {sets}, updated_at = NOW() WHERE id = %s", vals)
        updated = True

    if not updated:
        return Response({'error': 'No fields to update'}, status=status.HTTP_400_BAD_REQUEST)

    content.save()
    logger.info(f'content.updated id={content_id}')

    return Response({'success': True, 'content': _serialize_content(content)})


# =============================================================================
# STEP 5: TRANSCODE
# =============================================================================

@api_view(['POST'])
@permission_classes([IsEducatorOrAdmin])
def content_transcode(request, content_id):
    """Queue content for HLS transcoding."""
    try:
        content = Content.objects.get(id=content_id)
    except Content.DoesNotExist:
        return Response({'error': 'Content not found'}, status=status.HTTP_404_NOT_FOUND)

    denied = _check_content_ownership(content, request.user)
    if denied:
        return denied

    with django_connection.cursor() as cursor:
        cursor.execute(
            "UPDATE content SET status = 'processing', hls_conversion_status = 'queued', updated_at = NOW() WHERE id = %s",
            [str(content_id)]
        )

    logger.info(f'content.transcode_queued id={content_id}')
    return Response({'success': True, 'status': 'queued', 'message': 'Content queued for transcoding'})


# =============================================================================
# STEP 6: PUBLISH / UNPUBLISH
# =============================================================================

@api_view(['POST'])
@permission_classes([IsEducatorOrAdmin])
def content_publish(request, content_id):
    """Publish content (make it live)."""
    try:
        content = Content.objects.get(id=content_id)
    except Content.DoesNotExist:
        return Response({'error': 'Content not found'}, status=status.HTTP_404_NOT_FOUND)

    denied = _check_content_ownership(content, request.user)
    if denied:
        return denied

    content.status = ContentStatus.PUBLISHED
    content.is_published = True
    content.save()

    logger.info(f'content.published id={content_id}')
    return Response({'success': True, 'content': _serialize_content(content), 'message': 'Content is now live!'})


@api_view(['POST'])
@permission_classes([IsEducatorOrAdmin])
def content_unpublish(request, content_id):
    """Unpublish content (set back to draft)."""
    try:
        content = Content.objects.get(id=content_id)
    except Content.DoesNotExist:
        return Response({'error': 'Content not found'}, status=status.HTTP_404_NOT_FOUND)

    denied = _check_content_ownership(content, request.user)
    if denied:
        return denied

    content.status = ContentStatus.DRAFT
    content.is_published = False
    content.save()

    logger.info(f'content.unpublished id={content_id}')
    return Response({'success': True, 'content': _serialize_content(content)})


# =============================================================================
# LIST / DETAIL / ARCHIVE
# =============================================================================

@api_view(['GET'])
@permission_classes([IsEducatorOrAdmin])
def content_list(request):
    """List all content with optional filters."""
    qs = Content.objects.select_related('category', 'expert').all()

    status_filter = request.GET.get('status')
    if status_filter:
        qs = qs.filter(status=status_filter)

    content_type = request.GET.get('content_type')
    if content_type:
        qs = qs.filter(content_type=content_type)

    search = request.GET.get('search')
    if search:
        qs = qs.filter(title__icontains=search)

    limit = _safe_int(request.GET.get('limit', 50), default=50, min_val=1, max_val=100)
    offset = _safe_int(request.GET.get('offset', 0), default=0, min_val=0)

    qs = qs.order_by('-created_at')[offset:offset + limit]

    return Response({
        'content': [_serialize_content(c) for c in qs],
        'total': len(qs),
    })


@api_view(['GET'])
@permission_classes([IsEducatorOrAdmin])
def content_detail(request, content_id):
    """Get single content item by ID."""
    try:
        content = Content.objects.select_related('category', 'expert').get(id=content_id)
    except Content.DoesNotExist:
        return Response({'error': 'Content not found'}, status=status.HTTP_404_NOT_FOUND)

    return Response({'content': _serialize_content(content)})


@api_view(['DELETE'])
@permission_classes([IsEducatorOrAdmin])
def content_archive(request, content_id):
    """Archive content (soft delete)."""
    try:
        content = Content.objects.get(id=content_id)
    except Content.DoesNotExist:
        return Response({'error': 'Content not found'}, status=status.HTTP_404_NOT_FOUND)

    denied = _check_content_ownership(content, request.user)
    if denied:
        return denied

    content.status = ContentStatus.ARCHIVED
    content.save()

    logger.info(f'content.archived id={content_id}')
    return Response({'success': True, 'message': 'Content archived'})
