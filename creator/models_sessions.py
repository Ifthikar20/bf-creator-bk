"""
Live Sessions models — creator-scheduled live sessions and user signups.

These are NEW tables managed by bf-creator-bk (managed=True).
"""

import uuid
from django.db import models
from django.conf import settings


class LiveSession(models.Model):
    """A live session scheduled by a creator."""

    class SessionStatus(models.TextChoices):
        SCHEDULED = 'scheduled', 'Scheduled'
        LIVE = 'live', 'Live'
        COMPLETED = 'completed', 'Completed'
        CANCELLED = 'cancelled', 'Cancelled'

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    creator = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='live_sessions',
    )
    title = models.CharField(max_length=500)
    description = models.TextField(blank=True, default='')
    scheduled_at = models.DateTimeField(db_index=True)
    duration_minutes = models.IntegerField(default=60)
    max_attendees = models.IntegerField(default=50)
    cover_image_url = models.TextField(null=True, blank=True)
    status = models.CharField(
        max_length=20,
        choices=SessionStatus.choices,
        default=SessionStatus.SCHEDULED,
        db_index=True,
    )
    meeting_link = models.TextField(blank=True, default='')
    tags = models.TextField(blank=True, default='')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'live_sessions'
        ordering = ['scheduled_at']

    def __str__(self):
        return f'{self.title} — {self.scheduled_at}'

    @property
    def signup_count(self):
        return self.signups.count()

    def to_dict(self):
        return {
            'id': str(self.id),
            'creator_id': str(self.creator_id),
            'creator_name': self.creator.display_name or self.creator.email,
            'title': self.title,
            'description': self.description,
            'scheduled_at': self.scheduled_at.isoformat(),
            'duration_minutes': self.duration_minutes,
            'max_attendees': self.max_attendees,
            'cover_image_url': self.cover_image_url,
            'status': self.status,
            'meeting_link': self.meeting_link,
            'tags': self.tags,
            'signup_count': self.signup_count,
            'is_full': self.signup_count >= self.max_attendees,
            'created_at': self.created_at.isoformat(),
            'updated_at': self.updated_at.isoformat(),
        }


class SessionSignup(models.Model):
    """A user signup for a live session."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    session = models.ForeignKey(
        LiveSession,
        on_delete=models.CASCADE,
        related_name='signups',
    )
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='session_signups',
    )
    signed_up_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'session_signups'
        unique_together = ('session', 'user')
        ordering = ['-signed_up_at']

    def __str__(self):
        return f'{self.user} → {self.session.title}'
