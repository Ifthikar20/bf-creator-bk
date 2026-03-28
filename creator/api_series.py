"""
Creator Portal — Series/Playlist Management API.

CRUD + episode management + thumbnail upload.
Migrated from betterbliss-auth/creator/api_series.py.
"""

import uuid
import re
import logging
import boto3
from botocore.config import Config as BotoConfig

from django.conf import settings as django_settings
from django.db import connection as django_connection

from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.response import Response

from creator.permissions import IsEducatorOrAdmin

logger = logging.getLogger(__name__)


def _generate_slug(title):
    slug = title.lower().strip()
    slug = re.sub(r'[^a-z0-9\s-]', '', slug)
    slug = re.sub(r'[\s_]+', '-', slug)
    return slug.strip('-')


def _serialize_series(row):
    """Serialize a series row (dict from raw SQL)."""
    result = {}
    for k, v in row.items():
        if isinstance(v, uuid.UUID):
            result[k] = str(v)
        elif hasattr(v, 'isoformat'):
            result[k] = v.isoformat()
        else:
            result[k] = v
    # Computed field for frontend compat (frontend uses series.is_published)
    result['is_published'] = result.get('status') == 'published'
    return result


# =============================================================================
# CRUD
# =============================================================================

@api_view(['GET'])
@permission_classes([IsEducatorOrAdmin])
def series_list(request):
    """List all series with episode counts."""
    limit = min(int(request.GET.get('limit', 50)), 100)
    offset = int(request.GET.get('offset', 0))

    with django_connection.cursor() as cursor:
        cursor.execute("""
            SELECT s.id, s.title, s.description, s.slug, s.thumbnail_url,
                   s.status, s.created_at, s.updated_at,
                   COUNT(c.id) as episode_count
            FROM content_series s
            LEFT JOIN content c ON c.series_id = s.id
            GROUP BY s.id
            ORDER BY s.created_at DESC
            LIMIT %s OFFSET %s
        """, [limit, offset])
        columns = [col[0] for col in cursor.description]
        rows = [dict(zip(columns, row)) for row in cursor.fetchall()]

    serialized = [_serialize_series(r) for r in rows]

    return Response({
        'series': serialized,
        'results': serialized,  # Alias for ContentUploadView compat
        'total': len(rows),
    })


@api_view(['GET'])
@permission_classes([IsEducatorOrAdmin])
def series_detail(request, series_id):
    """Get series with all episodes."""
    with django_connection.cursor() as cursor:
        cursor.execute(
            "SELECT * FROM content_series WHERE id = %s", [str(series_id)]
        )
        columns = [col[0] for col in cursor.description]
        row = cursor.fetchone()

        if not row:
            return Response({'error': 'Series not found'}, status=status.HTTP_404_NOT_FOUND)

        series = _serialize_series(dict(zip(columns, row)))

        cursor.execute("""
            SELECT c.id, c.title, c.content_type, c.episode_number,
                   c.duration_seconds, c.thumbnail_url, c.status,
                   e.name as instructor_name
            FROM content c
            LEFT JOIN experts e ON c.expert_id = e.id
            WHERE c.series_id = %s
            ORDER BY c.episode_number
        """, [str(series_id)])
        ep_columns = [col[0] for col in cursor.description]
        episodes = [_serialize_series(dict(zip(ep_columns, r))) for r in cursor.fetchall()]

    series['episodes'] = episodes
    return Response({'series': series})


@api_view(['POST'])
@permission_classes([IsEducatorOrAdmin])
def series_create(request):
    """Create a new series."""
    title = request.data.get('title', '').strip()
    if not title:
        return Response({'error': 'title is required'}, status=status.HTTP_400_BAD_REQUEST)

    series_id = str(uuid.uuid4())
    slug = _generate_slug(title)

    with django_connection.cursor() as cursor:
        cursor.execute("SELECT id FROM content_series WHERE slug = %s", [slug])
        if cursor.fetchone():
            slug = f"{slug}-{series_id[:8]}"

        cursor.execute("""
            INSERT INTO content_series (id, title, slug, description, status)
            VALUES (%s, %s, %s, %s, 'draft')
            RETURNING id, title, slug, description, status, created_at
        """, [series_id, title, slug, request.data.get('description', '')])

        columns = [col[0] for col in cursor.description]
        row = dict(zip(columns, cursor.fetchone()))

    logger.info(f'series.created id={series_id}')
    return Response({
        'success': True,
        'series': _serialize_series(row),
    }, status=status.HTTP_201_CREATED)


@api_view(['PUT'])
@permission_classes([IsEducatorOrAdmin])
def series_update(request, series_id):
    """Update series metadata."""
    updatable = ['title', 'description', 'status']
    sets = []
    vals = []

    for field in updatable:
        if field in request.data:
            sets.append(f"{field} = %s")
            vals.append(request.data[field])

    for flag in ('show_on_explore', 'show_on_meditate'):
        if flag in request.data:
            sets.append(f"{flag} = %s")
            vals.append(request.data[flag])

    if not sets:
        return Response({'error': 'No fields to update'}, status=status.HTTP_400_BAD_REQUEST)

    sets.append("updated_at = NOW()")
    vals.append(str(series_id))

    with django_connection.cursor() as cursor:
        cursor.execute(
            f"UPDATE content_series SET {', '.join(sets)} WHERE id = %s RETURNING *",
            vals
        )
        row = cursor.fetchone()
        if not row:
            return Response({'error': 'Series not found'}, status=status.HTTP_404_NOT_FOUND)
        columns = [col[0] for col in cursor.description]
        series = _serialize_series(dict(zip(columns, row)))

    logger.info(f'series.updated id={series_id}')
    return Response({'success': True, 'series': series})


# =============================================================================
# EPISODE MANAGEMENT
# =============================================================================

@api_view(['POST'])
@permission_classes([IsEducatorOrAdmin])
def series_add_episode(request, series_id):
    """Add existing content as an episode to the series."""
    content_id = request.data.get('content_id')
    episode_number = request.data.get('episode_number')

    if not content_id:
        return Response({'error': 'content_id is required'}, status=status.HTTP_400_BAD_REQUEST)

    with django_connection.cursor() as cursor:
        cursor.execute("SELECT id FROM content_series WHERE id = %s", [str(series_id)])
        if not cursor.fetchone():
            return Response({'error': 'Series not found'}, status=status.HTTP_404_NOT_FOUND)

        if not episode_number:
            cursor.execute(
                "SELECT COALESCE(MAX(episode_number), 0) + 1 FROM content WHERE series_id = %s",
                [str(series_id)]
            )
            episode_number = cursor.fetchone()[0]

        cursor.execute(
            "UPDATE content SET series_id = %s, episode_number = %s, updated_at = NOW() WHERE id = %s",
            [str(series_id), episode_number, str(content_id)]
        )

    logger.info(f'series.episode_added series={series_id} content={content_id}')
    return Response({
        'success': True,
        'episode_number': episode_number,
    }, status=status.HTTP_201_CREATED)


@api_view(['DELETE'])
@permission_classes([IsEducatorOrAdmin])
def series_remove_episode(request, series_id, content_id):
    """Remove content from series."""
    with django_connection.cursor() as cursor:
        cursor.execute(
            "UPDATE content SET series_id = NULL, episode_number = NULL, updated_at = NOW() WHERE id = %s AND series_id = %s",
            [str(content_id), str(series_id)]
        )

    logger.info(f'series.episode_removed series={series_id} content={content_id}')
    return Response({'success': True, 'message': 'Episode removed'})


@api_view(['PUT'])
@permission_classes([IsEducatorOrAdmin])
def series_reorder_episodes(request, series_id):
    """Reorder episodes."""
    episode_ids = request.data.get('episode_ids', [])
    if not episode_ids:
        return Response({'error': 'episode_ids is required'}, status=status.HTTP_400_BAD_REQUEST)

    with django_connection.cursor() as cursor:
        for idx, cid in enumerate(episode_ids, 1):
            cursor.execute(
                "UPDATE content SET episode_number = %s WHERE id = %s AND series_id = %s",
                [idx, str(cid), str(series_id)]
            )

    logger.info(f'series.reordered id={series_id}')
    return Response({'success': True, 'message': f'Reordered {len(episode_ids)} episodes'})


# =============================================================================
# SERIES THUMBNAIL
# =============================================================================

@api_view(['POST'])
@permission_classes([IsEducatorOrAdmin])
def series_upload_thumbnail(request, series_id):
    """Get presigned URL for series thumbnail upload."""
    s3_key = f"series-thumbnails/{series_id}.jpg"

    try:
        s3 = boto3.client(
            's3',
            region_name=getattr(django_settings, 'AWS_REGION', 'us-east-1'),
            config=BotoConfig(signature_version='s3v4'),
        )
        bucket = getattr(django_settings, 'VIDEO_BUCKET_NAME', 'betterbliss-videos-production')
        presigned_url = s3.generate_presigned_url(
            'put_object',
            Params={'Bucket': bucket, 'Key': s3_key},
            ExpiresIn=3600,
        )
    except Exception as e:
        logger.error(f's3.series_thumbnail failed id={series_id}: {e}')
        return Response({'error': 'Failed to generate upload URL'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    return Response({'upload_url': presigned_url, 's3_key': s3_key, 'expires_in': 3600})


@api_view(['POST'])
@permission_classes([IsEducatorOrAdmin])
def series_confirm_thumbnail(request, series_id):
    """Confirm series thumbnail upload."""
    s3_key = request.data.get('s3_key', '')
    if not s3_key:
        return Response({'error': 's3_key is required'}, status=status.HTTP_400_BAD_REQUEST)

    cdn = getattr(django_settings, 'CLOUDFRONT_DOMAIN', 'd2f89dacgjld08.cloudfront.net')
    with django_connection.cursor() as cursor:
        cursor.execute(
            "UPDATE content_series SET thumbnail_url = %s, updated_at = NOW() WHERE id = %s",
            [f"https://{cdn}/{s3_key}", str(series_id)]
        )

    return Response({'success': True, 'thumbnail_key': s3_key})


# =============================================================================
# PUBLISH / UNPUBLISH SERIES
# =============================================================================

@api_view(['POST'])
@permission_classes([IsEducatorOrAdmin])
def series_publish(request, series_id):
    """Publish a series."""
    with django_connection.cursor() as cursor:
        cursor.execute(
            "UPDATE content_series SET status = 'published', updated_at = NOW() WHERE id = %s RETURNING id, title",
            [str(series_id)]
        )
        row = cursor.fetchone()
        if not row:
            return Response({'error': 'Series not found'}, status=status.HTTP_404_NOT_FOUND)

    logger.info(f'series.published id={series_id}')
    return Response({'success': True, 'message': 'Series published'})


@api_view(['POST'])
@permission_classes([IsEducatorOrAdmin])
def series_unpublish(request, series_id):
    """Unpublish a series."""
    with django_connection.cursor() as cursor:
        cursor.execute(
            "UPDATE content_series SET status = 'draft', updated_at = NOW() WHERE id = %s RETURNING id",
            [str(series_id)]
        )
        if not cursor.fetchone():
            return Response({'error': 'Series not found'}, status=status.HTTP_404_NOT_FOUND)

    logger.info(f'series.unpublished id={series_id}')
    return Response({'success': True, 'message': 'Series unpublished'})
