"""
BetterFeel Creator Backend — URL Configuration.

API routes:
  /auth/*            — Login, register, me, logout
  /api/creator/*     — Content, instructors, categories, series, dashboard
  /api/creator/*     — Earnings, Stripe Connect
  /health/           — Health check
"""

from django.contrib import admin
from django.urls import path, include
from django.http import JsonResponse


def health_check(request):
    return JsonResponse({
        'status': 'healthy',
        'service': 'bf-creator-bk',
        'version': '1.0.0',
    })


urlpatterns = [
    # Health check
    path('health/', health_check, name='health-check'),
    path('health', health_check, name='health-check-no-slash'),

    # Django admin (for superusers only)
    path('admin/', admin.site.urls),

    # Auth (login, register, me, logout)
    path('auth/', include('accounts.urls')),

    # Creator APIs (content, instructors, categories, series, dashboard)
    path('api/creator/', include('creator.urls')),

    # Payouts (earnings, Stripe Connect)
    path('api/creator/', include('payouts.urls')),
]
