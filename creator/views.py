"""
Creator Portal — Dashboard and upload URL views.

Migrated from betterbliss-auth/creator/views.py.
"""

import uuid
import logging
import boto3
from django.conf import settings as django_settings
from django.db.models import Sum
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from creator.models import Content, BlogPost, ContentStatus

logger = logging.getLogger(__name__)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def educator_dashboard(request):
    """Educator dashboard — summary stats for the logged-in educator."""
    user = request.user

    my_content = Content.objects.filter(submitted_by=user)
    my_blogs = BlogPost.objects.filter(author=user)

    content_stats = {
        'total_content': my_content.count(),
        'published': my_content.filter(status=ContentStatus.PUBLISHED).count(),
        'pending_review': my_content.filter(status=ContentStatus.PENDING_REVIEW).count(),
        'drafts': my_content.filter(status=ContentStatus.DRAFT).count(),
        'rejected': my_content.filter(status=ContentStatus.REJECTED).count(),
        'total_views': my_content.aggregate(total=Sum('view_count'))['total'] or 0,
    }

    blog_stats = {
        'total_posts': my_blogs.count(),
        'published': my_blogs.filter(status=ContentStatus.PUBLISHED).count(),
        'pending_review': my_blogs.filter(status=ContentStatus.PENDING_REVIEW).count(),
        'drafts': my_blogs.filter(status=ContentStatus.DRAFT).count(),
        'total_views': my_blogs.aggregate(total=Sum('view_count'))['total'] or 0,
    }

    top_content = list(
        my_content.filter(status=ContentStatus.PUBLISHED)
        .order_by('-view_count')[:5]
        .values('id', 'title', 'content_type', 'view_count')
    )
    for item in top_content:
        item['id'] = str(item['id'])

    return Response({
        'success': True,
        'educator': {
            'id': str(user.id),
            'name': user.display_name or user.email,
            'email': user.email,
        },
        # Flat keys for frontend DashboardView compatibility
        'total_content': content_stats['total_content'],
        'published_content': content_stats['published'],
        'pending_review': content_stats['pending_review'],
        'total_views': content_stats['total_views'],
        # Detailed stats
        'content_stats': content_stats,
        'blog_stats': blog_stats,
        'top_content': top_content,
    })


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def get_upload_url(request):
    """Generate S3 presigned URL for media upload."""
    user = request.user
    filename = request.data.get('filename', '')
    file_content_type = request.data.get('content_type', 'application/octet-stream')
    upload_type = request.data.get('upload_type', 'media')

    if not filename:
        return Response({
            'success': False,
            'error': {'code': 'MISSING_FILENAME', 'message': 'filename is required'}
        }, status=400)

    file_ext = filename.rsplit('.', 1)[-1] if '.' in filename else ''
    unique_key = f"uploads/{user.id}/{upload_type}/{uuid.uuid4()}.{file_ext}"

    try:
        s3_client = boto3.client('s3', region_name=django_settings.AWS_REGION)
        presigned_url = s3_client.generate_presigned_url(
            'put_object',
            Params={
                'Bucket': django_settings.VIDEO_BUCKET_NAME,
                'Key': unique_key,
                'ContentType': file_content_type,
            },
            ExpiresIn=3600,
        )

        logger.info(f'Generated upload URL: {unique_key}')

        return Response({
            'success': True,
            'upload_url': presigned_url,
            's3_key': unique_key,
            'expires_in': 3600,
        })

    except Exception as e:
        logger.error(f'Failed to generate upload URL: {e}')
        return Response({
            'success': False,
            'error': {'code': 'UPLOAD_ERROR', 'message': 'Failed to generate upload URL'}
        }, status=500)
