"""
Payouts models — content view tracking and payout records.

ContentView: daily aggregate of views per content item per creator.
CreatorPayout: records each payout transfer to a creator via Stripe.
"""

import uuid
from django.db import models
from django.conf import settings


class ContentView(models.Model):
    """Daily aggregate of views for a specific content item."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    creator = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='content_views',
    )
    content_id = models.UUIDField(db_index=True)
    view_count = models.PositiveIntegerField(default=0)
    date = models.DateField(db_index=True)

    class Meta:
        db_table = 'creator_content_views'
        managed = False
        unique_together = ('content_id', 'date')
        ordering = ['-date']

    def __str__(self):
        return f'{self.content_id} - {self.date}: {self.view_count} views'


class PayoutStatus(models.TextChoices):
    PENDING = 'pending', 'Pending'
    PROCESSING = 'processing', 'Processing'
    COMPLETED = 'completed', 'Completed'
    FAILED = 'failed', 'Failed'


class CreatorPayout(models.Model):
    """Records each payout made to a creator via Stripe Connect."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    creator = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='payouts',
    )
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    views_count = models.PositiveIntegerField(default=0)
    description = models.CharField(max_length=500, blank=True, default='')
    stripe_transfer_id = models.CharField(max_length=255, blank=True, null=True)
    status = models.CharField(
        max_length=20,
        choices=PayoutStatus.choices,
        default=PayoutStatus.PENDING,
    )
    created_at = models.DateTimeField(auto_now_add=True)
    completed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = 'creator_payouts'
        managed = False
        ordering = ['-created_at']

    def __str__(self):
        return f'{self.creator} - ${self.amount} ({self.status})'
