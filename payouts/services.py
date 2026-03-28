"""
Payout business logic — rate calculation, Stripe transfers, view tracking.

Payout rates:
  Base:  $0.035 per view
  Bonus: +$0.005 per view when cycle views exceed 10,000
  Threshold: 10,000 views triggers a payout
"""

import logging
from datetime import date, timedelta
from decimal import Decimal

import stripe
from django.conf import settings
from django.db.models import Sum
from django.utils import timezone

from payouts.models import ContentView, CreatorPayout, PayoutStatus

logger = logging.getLogger(__name__)

# Payout configuration
BASE_RATE = Decimal('0.035')
BONUS_RATE = Decimal('0.005')
VIEW_THRESHOLD = 10000
BONUS_THRESHOLD = 10000


def calculate_payout_amount(views):
    """Calculate the payout amount for a given number of views."""
    amount = Decimal(views) * BASE_RATE
    if views > BONUS_THRESHOLD:
        amount += Decimal(views) * BONUS_RATE
    return amount.quantize(Decimal('0.01'))


def get_unpaid_views(creator):
    """Get total views that have not yet been paid out."""
    last_payout = CreatorPayout.objects.filter(
        creator=creator,
        status=PayoutStatus.COMPLETED,
    ).first()

    views_qs = ContentView.objects.filter(creator=creator)
    if last_payout:
        views_qs = views_qs.filter(date__gt=last_payout.completed_at.date())

    total = views_qs.aggregate(total=Sum('view_count'))['total'] or 0
    return total


def check_and_create_payout(creator):
    """Check if a creator has hit the view threshold and create a Stripe transfer."""
    if not creator.stripe_onboarding_complete or not creator.stripe_account_id:
        logger.info(f'Creator {creator.id} not connected to Stripe, skipping payout.')
        return None

    unpaid_views = get_unpaid_views(creator)
    if unpaid_views < VIEW_THRESHOLD:
        logger.info(f'Creator {creator.id} has {unpaid_views} views, below threshold.')
        return None

    amount = calculate_payout_amount(unpaid_views)
    amount_cents = int(amount * 100)

    month_name = date.today().strftime('%B')
    payout = CreatorPayout.objects.create(
        creator=creator,
        amount=amount,
        views_count=unpaid_views,
        description=f'{month_name} payout -- milestone reached',
        status=PayoutStatus.PROCESSING,
    )

    try:
        stripe.api_key = settings.STRIPE_SECRET_KEY
        transfer = stripe.Transfer.create(
            amount=amount_cents,
            currency='usd',
            destination=creator.stripe_account_id,
            description=f'BetterFeel creator payout for {creator.display_name or creator.email}',
            metadata={
                'payout_id': str(payout.id),
                'creator_id': str(creator.id),
                'views': unpaid_views,
            },
        )
        payout.stripe_transfer_id = transfer.id
        payout.status = PayoutStatus.COMPLETED
        payout.completed_at = timezone.now()
        payout.save()
        logger.info(f'Payout {payout.id} completed: ${amount} to {creator.email}')
        return payout

    except stripe.error.StripeError as e:
        payout.status = PayoutStatus.FAILED
        payout.save()
        logger.error(f'Stripe transfer failed for payout {payout.id}: {e}')
        return payout


def record_content_view(content_id, creator_id):
    """Record a view for a content item (daily aggregation)."""
    today = date.today()
    view, created = ContentView.objects.get_or_create(
        content_id=content_id,
        date=today,
        defaults={'creator_id': creator_id, 'view_count': 1},
    )
    if not created:
        view.view_count += 1
        view.save(update_fields=['view_count'])
    return view


def get_earnings_data(creator):
    """Build the full earnings data payload for a creator."""
    total_earned = CreatorPayout.objects.filter(
        creator=creator,
        status=PayoutStatus.COMPLETED,
    ).aggregate(total=Sum('amount'))['total'] or Decimal('0.00')

    unpaid_views = get_unpaid_views(creator)
    pending_balance = calculate_payout_amount(unpaid_views)

    payouts = CreatorPayout.objects.filter(creator=creator)[:20]
    payout_history = [
        {
            'id': str(p.id),
            'date': p.created_at.strftime('%Y-%m-%d'),
            'amount': float(p.amount),
            'views': p.views_count,
            'status': p.status,
            'description': p.description,
        }
        for p in payouts
    ]

    monthly_earnings = []
    month_labels = []
    today = date.today()
    for i in range(5, -1, -1):
        month_start = (today.replace(day=1) - timedelta(days=30 * i)).replace(day=1)
        if i > 0:
            month_end = (month_start.replace(day=28) + timedelta(days=4)).replace(day=1)
        else:
            month_end = today + timedelta(days=1)

        month_total = CreatorPayout.objects.filter(
            creator=creator,
            status=PayoutStatus.COMPLETED,
            completed_at__gte=month_start,
            completed_at__lt=month_end,
        ).aggregate(total=Sum('amount'))['total'] or Decimal('0.00')

        monthly_earnings.append(float(month_total))
        month_labels.append(month_start.strftime('%b'))

    return {
        'totalEarned': float(total_earned),
        'pendingBalance': float(pending_balance),
        'nextPayout': None,
        'viewsThreshold': VIEW_THRESHOLD,
        'currentViews': unpaid_views,
        'stripeConnected': creator.stripe_onboarding_complete,
        'payoutHistory': payout_history,
        'monthlyEarnings': monthly_earnings,
        'monthLabels': month_labels,
        'payoutRate': {
            'baseRate': float(BASE_RATE),
            'bonusRate': float(BONUS_RATE),
            'bonusThreshold': BONUS_THRESHOLD,
        },
    }
