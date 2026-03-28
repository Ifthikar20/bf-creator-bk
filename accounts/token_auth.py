"""
Expiring Token Authentication — 7-day token lifecycle.

Extends DRF's built-in TokenAuthentication to reject tokens
older than TOKEN_EXPIRY_DAYS.
"""

from datetime import timedelta
from django.conf import settings as django_settings
from django.utils import timezone
from rest_framework import exceptions
from rest_framework.authentication import TokenAuthentication


class ExpiringTokenAuthentication(TokenAuthentication):
    """Token auth with configurable expiry (default 7 days)."""

    def authenticate_credentials(self, key):
        user, token = super().authenticate_credentials(key)

        expiry_days = getattr(django_settings, 'TOKEN_EXPIRY_DAYS', 7)
        token_age = timezone.now() - token.created

        if token_age > timedelta(days=expiry_days):
            token.delete()
            raise exceptions.AuthenticationFailed(
                'Token has expired. Please log in again.'
            )

        return user, token
