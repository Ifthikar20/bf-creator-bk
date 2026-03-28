"""
Accounts views — Login, register, me, logout for the Creator Portal.

These endpoints serve the Vue.js Creator Studio frontend.
"""

import logging
from django.contrib.auth import authenticate
from rest_framework import status
from rest_framework.authtoken.models import Token
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response

from accounts.models import CreatorUser, UserRole

logger = logging.getLogger(__name__)


@api_view(['POST'])
@permission_classes([AllowAny])
def login_view(request):
    """
    Email/password login. Returns a DRF token.

    POST /auth/login/
    Body: { "email": "...", "password": "..." }
    """
    email = request.data.get('email', '').strip().lower()
    password = request.data.get('password', '')

    if not email or not password:
        return Response(
            {'error': 'Email and password are required'},
            status=status.HTTP_400_BAD_REQUEST,
        )

    user = authenticate(request, email=email, password=password)

    if user is None:
        return Response(
            {'error': 'Invalid email or password'},
            status=status.HTTP_401_UNAUTHORIZED,
        )

    if user.status != 'active':
        return Response(
            {'error': 'Account is not active'},
            status=status.HTTP_403_FORBIDDEN,
        )

    # Get or create token
    token, _ = Token.objects.get_or_create(user=user)

    logger.info(f'Creator login: {user.email}')

    return Response({
        'token': token.key,
        'user': user.to_dict(),
    })


@api_view(['POST'])
@permission_classes([AllowAny])
def register_view(request):
    """
    Register a new creator account.

    POST /auth/register/
    Body: { "email": "...", "password": "...", "display_name": "..." }
    """
    email = request.data.get('email', '').strip().lower()
    password = request.data.get('password', '')
    display_name = request.data.get('display_name', '').strip()

    if not email or not password:
        return Response(
            {'error': 'Email and password are required'},
            status=status.HTTP_400_BAD_REQUEST,
        )

    if len(password) < 8:
        return Response(
            {'error': 'Password must be at least 8 characters'},
            status=status.HTTP_400_BAD_REQUEST,
        )

    if CreatorUser.objects.filter(email=email).exists():
        return Response(
            {'error': 'An account with this email already exists'},
            status=status.HTTP_409_CONFLICT,
        )

    user = CreatorUser.objects.create_user(
        email=email,
        password=password,
        display_name=display_name or email.split('@')[0],
        role=UserRole.EDUCATOR,
    )

    token, _ = Token.objects.get_or_create(user=user)

    logger.info(f'Creator registered: {user.email}')

    return Response({
        'token': token.key,
        'user': user.to_dict(),
    }, status=status.HTTP_201_CREATED)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def me_view(request):
    """
    Return current user info.

    GET /auth/me/
    """
    return Response({'user': request.user.to_dict()})


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def logout_view(request):
    """
    Logout — delete the auth token.

    POST /auth/logout/
    """
    try:
        request.user.auth_token.delete()
    except Exception:
        pass

    return Response({'success': True})


@api_view(['PUT'])
@permission_classes([IsAuthenticated])
def profile_view(request):
    """
    Update profile.

    PUT /auth/profile/
    Body: { "display_name": "..." }
    """
    user = request.user
    updated = False

    if 'display_name' in request.data:
        user.display_name = request.data['display_name']
        updated = True

    if 'avatar_url' in request.data:
        user.avatar_url = request.data['avatar_url']
        updated = True

    if updated:
        user.save()

    return Response({'user': user.to_dict()})
