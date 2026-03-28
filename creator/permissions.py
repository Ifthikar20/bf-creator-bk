"""
Creator Portal permissions — role-based access control.

Classes:
    IsEducatorOrAdmin — restricts access to users with 'educator' or 'admin' role
    IsContentOwnerOrAdmin — object-level check: user must own the content or be admin
"""

import logging
from rest_framework.permissions import BasePermission

logger = logging.getLogger(__name__)


class IsEducatorOrAdmin(BasePermission):
    """Restrict Creator portal access to educators and admins only."""

    message = 'Creator portal access requires an educator or admin account.'

    def has_permission(self, request, view):
        if not request.user or not request.user.is_authenticated:
            return False

        user = request.user
        return (
            getattr(user, 'role', None) in ('educator', 'admin')
            or getattr(user, 'is_staff', False)
        )


class IsContentOwnerOrAdmin(BasePermission):
    """Object-level permission: user must be the content creator OR an admin."""

    message = 'You can only modify content you created.'

    def has_object_permission(self, request, view, obj):
        user = request.user

        if getattr(user, 'role', None) == 'admin' or getattr(user, 'is_staff', False):
            return True

        submitted_by = getattr(obj, 'submitted_by', None)
        if submitted_by is not None and submitted_by == user:
            return True

        logger.warning(
            f'DENIED content.ownership resource={getattr(obj, "id", "?")} user={user.id}'
        )
        return False
