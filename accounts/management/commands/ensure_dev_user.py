"""
Management command to ensure a dev user exists for auto-login.

Usage: python manage.py ensure_dev_user
Prints the auth token to stdout so the run script can capture it.
"""

import sys
from django.core.management.base import BaseCommand
from rest_framework.authtoken.models import Token
from accounts.models import CreatorUser, UserRole


class Command(BaseCommand):
    help = 'Create/ensure dev user and print auth token'

    DEV_EMAIL = 'creator@dev.local'
    DEV_PASSWORD = 'devpass123'
    DEV_NAME = 'Dev Creator'

    def handle(self, *args, **options):
        user, created = CreatorUser.objects.get_or_create(
            email=self.DEV_EMAIL,
            defaults={
                'display_name': self.DEV_NAME,
                'role': UserRole.EDUCATOR,
                'status': 'active',
            },
        )

        if created:
            user.set_password(self.DEV_PASSWORD)
            user.save()
            self.stderr.write(self.style.SUCCESS(f'Created dev user: {self.DEV_EMAIL}'))
        else:
            self.stderr.write(self.style.SUCCESS(f'Dev user exists: {self.DEV_EMAIL}'))

        # Ensure active token
        Token.objects.filter(user=user).delete()
        token = Token.objects.create(user=user)

        # Print ONLY the token to stdout (script captures this)
        sys.stdout.write(token.key)
        sys.stdout.flush()
