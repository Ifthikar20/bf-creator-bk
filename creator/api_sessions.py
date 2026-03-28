"""
Live Sessions API — schedule, manage, and sign up for live sessions.

Mounted at /api/creator/sessions/ in creator/urls.py.
"""

import logging
from datetime import datetime, timezone

from django.db.models import Q
from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from creator.models_sessions import LiveSession, SessionSignup

logger = logging.getLogger(__name__)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def session_list(request):
    """
    List live sessions.

    GET /api/creator/sessions/
    Query params:
      ?filter=upcoming|past|mine  (default: all)
      ?month=2026-03               (filter by month)
    """
    qs = LiveSession.objects.select_related('creator')

    # Filter by type
    filter_type = request.query_params.get('filter', '')
    now = datetime.now(timezone.utc)

    if filter_type == 'upcoming':
        qs = qs.filter(scheduled_at__gte=now).exclude(status='cancelled')
    elif filter_type == 'past':
        qs = qs.filter(scheduled_at__lt=now)
    elif filter_type == 'mine':
        qs = qs.filter(creator=request.user)

    # Filter by month (YYYY-MM)
    month = request.query_params.get('month', '')
    if month:
        try:
            year, mo = month.split('-')
            qs = qs.filter(
                scheduled_at__year=int(year),
                scheduled_at__month=int(mo),
            )
        except (ValueError, IndexError):
            pass

    sessions = qs[:100]

    # Check which sessions the current user has signed up for
    signed_up_ids = set(
        SessionSignup.objects.filter(
            user=request.user,
            session__in=sessions,
        ).values_list('session_id', flat=True)
    )

    data = []
    for s in sessions:
        d = s.to_dict()
        d['user_signed_up'] = s.id in signed_up_ids
        data.append(d)

    return Response({'sessions': data})


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def session_create(request):
    """
    Create a new live session.

    POST /api/creator/sessions/create/
    Body: { title, description, scheduled_at, duration_minutes, max_attendees, meeting_link, tags }
    """
    title = request.data.get('title', '').strip()
    if not title:
        return Response({'error': 'Title is required'}, status=status.HTTP_400_BAD_REQUEST)

    scheduled_at = request.data.get('scheduled_at')
    if not scheduled_at:
        return Response({'error': 'Scheduled time is required'}, status=status.HTTP_400_BAD_REQUEST)

    try:
        if isinstance(scheduled_at, str):
            scheduled_at = datetime.fromisoformat(scheduled_at.replace('Z', '+00:00'))
    except (ValueError, TypeError):
        return Response({'error': 'Invalid date format'}, status=status.HTTP_400_BAD_REQUEST)

    session = LiveSession.objects.create(
        creator=request.user,
        title=title,
        description=request.data.get('description', ''),
        scheduled_at=scheduled_at,
        duration_minutes=request.data.get('duration_minutes', 60),
        max_attendees=request.data.get('max_attendees', 50),
        cover_image_url=request.data.get('cover_image_url'),
        meeting_link=request.data.get('meeting_link', ''),
        tags=request.data.get('tags', ''),
    )

    logger.info(f'Session created: {session.title} by {request.user.email}')
    return Response({'session': session.to_dict()}, status=status.HTTP_201_CREATED)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def session_detail(request, session_id):
    """
    Get session detail.

    GET /api/creator/sessions/<id>/
    """
    try:
        session = LiveSession.objects.select_related('creator').get(id=session_id)
    except LiveSession.DoesNotExist:
        return Response({'error': 'Session not found'}, status=status.HTTP_404_NOT_FOUND)

    data = session.to_dict()
    data['user_signed_up'] = SessionSignup.objects.filter(
        session=session, user=request.user,
    ).exists()

    # Include attendee list if the requester is the creator
    if session.creator_id == request.user.id:
        data['attendees'] = [
            {
                'user_id': str(s.user_id),
                'display_name': s.user.display_name or s.user.email,
                'signed_up_at': s.signed_up_at.isoformat(),
            }
            for s in session.signups.select_related('user')[:100]
        ]

    return Response({'session': data})


@api_view(['PUT'])
@permission_classes([IsAuthenticated])
def session_update(request, session_id):
    """
    Update a session (creator-only).

    PUT /api/creator/sessions/<id>/update/
    """
    try:
        session = LiveSession.objects.get(id=session_id, creator=request.user)
    except LiveSession.DoesNotExist:
        return Response({'error': 'Session not found'}, status=status.HTTP_404_NOT_FOUND)

    for field in ['title', 'description', 'duration_minutes', 'max_attendees',
                  'cover_image_url', 'meeting_link', 'tags', 'status']:
        if field in request.data:
            setattr(session, field, request.data[field])

    if 'scheduled_at' in request.data:
        try:
            val = request.data['scheduled_at']
            if isinstance(val, str):
                val = datetime.fromisoformat(val.replace('Z', '+00:00'))
            session.scheduled_at = val
        except (ValueError, TypeError):
            return Response({'error': 'Invalid date format'}, status=status.HTTP_400_BAD_REQUEST)

    session.save()
    return Response({'session': session.to_dict()})


@api_view(['DELETE'])
@permission_classes([IsAuthenticated])
def session_delete(request, session_id):
    """
    Cancel/delete a session (creator-only).

    DELETE /api/creator/sessions/<id>/delete/
    """
    try:
        session = LiveSession.objects.get(id=session_id, creator=request.user)
    except LiveSession.DoesNotExist:
        return Response({'error': 'Session not found'}, status=status.HTTP_404_NOT_FOUND)

    session.status = 'cancelled'
    session.save()
    return Response({'success': True})


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def session_signup(request, session_id):
    """
    Sign up for a session.

    POST /api/creator/sessions/<id>/signup/
    """
    try:
        session = LiveSession.objects.get(id=session_id)
    except LiveSession.DoesNotExist:
        return Response({'error': 'Session not found'}, status=status.HTTP_404_NOT_FOUND)

    if session.status == 'cancelled':
        return Response({'error': 'Session has been cancelled'}, status=status.HTTP_400_BAD_REQUEST)

    if session.signup_count >= session.max_attendees:
        return Response({'error': 'Session is full'}, status=status.HTTP_400_BAD_REQUEST)

    _, created = SessionSignup.objects.get_or_create(
        session=session, user=request.user,
    )

    if not created:
        return Response({'error': 'Already signed up'}, status=status.HTTP_409_CONFLICT)

    logger.info(f'Signup: {request.user.email} → {session.title}')
    return Response({'success': True, 'signup_count': session.signup_count})


@api_view(['DELETE'])
@permission_classes([IsAuthenticated])
def session_cancel_signup(request, session_id):
    """
    Cancel signup for a session.

    DELETE /api/creator/sessions/<id>/cancel-signup/
    """
    deleted, _ = SessionSignup.objects.filter(
        session_id=session_id, user=request.user,
    ).delete()

    if not deleted:
        return Response({'error': 'Not signed up'}, status=status.HTTP_404_NOT_FOUND)

    session = LiveSession.objects.get(id=session_id)
    return Response({'success': True, 'signup_count': session.signup_count})
