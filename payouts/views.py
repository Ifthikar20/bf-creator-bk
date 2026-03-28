"""
Payouts API views — Stripe Connect onboarding, earnings data, webhook handler.

Migrated from betterfeel-creator-backend/payouts/views.py.
"""

import json
import logging

import stripe
from django.conf import settings
from django.http import HttpResponse
from django.views.decorators.csrf import csrf_exempt
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated, AllowAny
from rest_framework.response import Response

from payouts.services import get_earnings_data

logger = logging.getLogger(__name__)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def stripe_connect(request):
    """Create a Stripe Connect account for the creator."""
    creator = request.user

    if creator.stripe_onboarding_complete:
        return Response({'error': 'Stripe already connected'}, status=400)

    stripe.api_key = settings.STRIPE_SECRET_KEY

    try:
        if not creator.stripe_account_id:
            account = stripe.Account.create(
                type='express',
                email=creator.email,
                metadata={
                    'creator_id': str(creator.id),
                    'platform': 'betterfeel',
                },
                capabilities={
                    'transfers': {'requested': True},
                },
            )
            creator.stripe_account_id = account.id
            creator.save(update_fields=['stripe_account_id'])

        return_url = settings.STRIPE_CONNECT_RETURN_URL
        account_link = stripe.AccountLink.create(
            account=creator.stripe_account_id,
            refresh_url=return_url,
            return_url=return_url,
            type='account_onboarding',
        )

        return Response({
            'onboarding_url': account_link.url,
            'account_id': creator.stripe_account_id,
        })

    except stripe.error.StripeError as e:
        logger.error(f'Stripe Connect error for creator {creator.id}: {e}')
        return Response({'error': str(e)}, status=500)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def stripe_status(request):
    """Check Stripe Connect status for the creator."""
    creator = request.user

    if not creator.stripe_account_id:
        return Response({
            'connected': False,
            'account_id': None,
            'details_submitted': False,
            'payouts_enabled': False,
        })

    try:
        stripe.api_key = settings.STRIPE_SECRET_KEY
        account = stripe.Account.retrieve(creator.stripe_account_id)

        if account.details_submitted and not creator.stripe_onboarding_complete:
            creator.stripe_onboarding_complete = True
            creator.save(update_fields=['stripe_onboarding_complete'])

        return Response({
            'connected': creator.stripe_onboarding_complete,
            'account_id': creator.stripe_account_id,
            'details_submitted': account.details_submitted,
            'payouts_enabled': account.payouts_enabled,
        })

    except stripe.error.StripeError as e:
        logger.error(f'Stripe status check failed for creator {creator.id}: {e}')
        return Response({
            'connected': creator.stripe_onboarding_complete,
            'account_id': creator.stripe_account_id,
            'details_submitted': False,
            'payouts_enabled': False,
        })


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def earnings(request):
    """Return full earnings data for the authenticated creator."""
    creator = request.user
    data = get_earnings_data(creator)
    return Response(data)


@csrf_exempt
@api_view(['POST'])
@permission_classes([AllowAny])
def stripe_webhook(request):
    """Handle Stripe webhook events."""
    payload = request.body
    sig_header = request.META.get('HTTP_STRIPE_SIGNATURE', '')

    webhook_secret = getattr(settings, 'STRIPE_WEBHOOK_SECRET', None)

    if webhook_secret:
        try:
            event = stripe.Webhook.construct_event(payload, sig_header, webhook_secret)
        except ValueError:
            logger.error('Stripe webhook: invalid payload')
            return HttpResponse(status=400)
        except stripe.error.SignatureVerificationError:
            logger.error('Stripe webhook: invalid signature')
            return HttpResponse(status=400)
    else:
        try:
            event = json.loads(payload)
        except json.JSONDecodeError:
            return HttpResponse(status=400)

    event_type = event.get('type', '') if isinstance(event, dict) else event.type
    event_data = event.get('data', {}).get('object', {}) if isinstance(event, dict) else event.data.object

    if event_type == 'account.updated':
        _handle_account_updated(event_data)
    elif event_type == 'transfer.paid':
        _handle_transfer_paid(event_data)
    elif event_type == 'transfer.failed':
        _handle_transfer_failed(event_data)

    return HttpResponse(status=200)


def _handle_account_updated(account_data):
    """Mark creator as onboarded when Stripe confirms details_submitted."""
    from accounts.models import CreatorUser

    account_id = account_data.get('id') if isinstance(account_data, dict) else account_data.id
    details_submitted = (
        account_data.get('details_submitted', False)
        if isinstance(account_data, dict)
        else getattr(account_data, 'details_submitted', False)
    )

    if details_submitted:
        try:
            creator = CreatorUser.objects.get(stripe_account_id=account_id)
            if not creator.stripe_onboarding_complete:
                creator.stripe_onboarding_complete = True
                creator.save(update_fields=['stripe_onboarding_complete'])
                logger.info(f'Creator {creator.id} Stripe onboarding completed via webhook')
        except CreatorUser.DoesNotExist:
            logger.warning(f'No creator found for Stripe account {account_id}')


def _handle_transfer_paid(transfer_data):
    """Update payout record when transfer is confirmed paid."""
    from payouts.models import CreatorPayout, PayoutStatus
    from django.utils import timezone

    transfer_id = transfer_data.get('id') if isinstance(transfer_data, dict) else transfer_data.id

    try:
        payout = CreatorPayout.objects.get(stripe_transfer_id=transfer_id)
        payout.status = PayoutStatus.COMPLETED
        payout.completed_at = timezone.now()
        payout.save(update_fields=['status', 'completed_at'])
        logger.info(f'Payout {payout.id} marked as completed via webhook')
    except CreatorPayout.DoesNotExist:
        logger.warning(f'No payout found for transfer {transfer_id}')


def _handle_transfer_failed(transfer_data):
    """Update payout record when transfer fails."""
    from payouts.models import CreatorPayout, PayoutStatus

    transfer_id = transfer_data.get('id') if isinstance(transfer_data, dict) else transfer_data.id

    try:
        payout = CreatorPayout.objects.get(stripe_transfer_id=transfer_id)
        payout.status = PayoutStatus.FAILED
        payout.save(update_fields=['status'])
        logger.error(f'Payout {payout.id} marked as failed via webhook')
    except CreatorPayout.DoesNotExist:
        logger.warning(f'No payout found for transfer {transfer_id}')
