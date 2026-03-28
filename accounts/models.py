"""
CreatorUser model — maps to the same auth_users table as betterbliss-auth.

managed = False: Django will NOT create/modify this table.
The table is owned and migrated by the betterbliss-auth project.
"""

import uuid
from django.db import models
from django.contrib.auth.models import AbstractUser, BaseUserManager


class UserRole(models.TextChoices):
    FREE_USER = 'free_user', 'Free User'
    PREMIUM_USER = 'premium_user', 'Premium User'
    EDUCATOR = 'educator', 'Educator'
    ADMIN = 'admin', 'Admin'


class SubscriptionTier(models.TextChoices):
    FREE = 'free', 'Free'
    BASIC = 'basic', 'Basic'
    PREMIUM = 'premium', 'Premium'


class CreatorUserManager(BaseUserManager):
    """Custom user manager — email as identifier."""

    def create_user(self, email, password=None, **extra_fields):
        if not email:
            raise ValueError('Email is required')
        email = self.normalize_email(email)
        extra_fields.setdefault('role', UserRole.EDUCATOR)
        extra_fields.setdefault('subscription_tier', SubscriptionTier.FREE)
        extra_fields.setdefault('status', 'active')

        user = self.model(email=email, **extra_fields)
        user.set_password(password)
        user.save(using=self._db)
        return user

    def create_superuser(self, email, password=None, **extra_fields):
        extra_fields.setdefault('is_staff', True)
        extra_fields.setdefault('is_superuser', True)
        extra_fields.setdefault('role', UserRole.ADMIN)
        return self.create_user(email, password, **extra_fields)


class CreatorUser(AbstractUser):
    """
    Maps to the auth_users table created by betterbliss-auth.

    This is NOT a separate user model — it reads/writes the same
    users table. managed=False ensures no migrations are generated.
    """

    # Override AbstractUser fields
    username = None
    email = models.EmailField(unique=True)

    # BetterBliss fields
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    display_name = models.CharField(max_length=255, blank=True, default='')
    avatar_url = models.TextField(null=True, blank=True)
    role = models.CharField(
        max_length=50,
        choices=UserRole.choices,
        default=UserRole.FREE_USER,
    )
    subscription_tier = models.CharField(
        max_length=50,
        choices=SubscriptionTier.choices,
        default=SubscriptionTier.FREE,
    )
    status = models.CharField(max_length=50, default='active')
    deletion_scheduled_at = models.DateTimeField(null=True, blank=True)
    subscription_ends_at = models.DateTimeField(null=True, blank=True)

    # Note: Stripe Connect fields are managed via the payouts app's own table.
    # Do NOT add stripe columns here — this table is managed=False.

    USERNAME_FIELD = 'email'
    REQUIRED_FIELDS = []

    objects = CreatorUserManager()

    class Meta:
        db_table = 'auth_users'
        managed = False  # Table owned by betterbliss-auth
        ordering = ['-date_joined']

    def __str__(self):
        return f'{self.display_name or self.email} ({self.email})'

    def to_dict(self):
        return {
            'id': str(self.id),
            'email': self.email,
            'display_name': self.display_name or self.email.split('@')[0],
            'avatar_url': self.avatar_url,
            'role': self.role,
            'subscription_tier': self.subscription_tier,
            'status': self.status,
            'created_at': self.date_joined.isoformat() if self.date_joined else None,
            'updated_at': self.last_login.isoformat() if self.last_login else None,
        }
