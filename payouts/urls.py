"""
Payouts URL configuration.

Mounted at /api/creator/ in creator_project/urls.py.
"""

from django.urls import path
from payouts import views

urlpatterns = [
    # Stripe Connect
    path('stripe/connect/', views.stripe_connect, name='stripe-connect'),
    path('stripe/status/', views.stripe_status, name='stripe-status'),

    # Earnings
    path('earnings/', views.earnings, name='creator-earnings'),

    # Webhook (no auth — uses Stripe signature verification)
    path('stripe/webhook/', views.stripe_webhook, name='stripe-webhook'),
]
