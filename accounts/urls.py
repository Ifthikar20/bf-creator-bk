"""
Accounts URL configuration.

Mounted at /auth/ in creator_project/urls.py.
"""

from django.urls import path
from accounts import views

urlpatterns = [
    path('login/', views.login_view, name='auth-login'),
    path('register/', views.register_view, name='auth-register'),
    path('me/', views.me_view, name='auth-me'),
    path('logout/', views.logout_view, name='auth-logout'),
    path('profile/', views.profile_view, name='auth-profile'),
]
