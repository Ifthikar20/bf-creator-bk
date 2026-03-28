"""
Creator Portal URL configuration.

Mounted at /api/creator/ in creator_project/urls.py.
"""

from django.urls import path
from creator import views
from creator import api_content, api_instructors, api_categories, api_series, api_sessions

urlpatterns = [
    # ── Dashboard ──
    path('dashboard/', views.educator_dashboard, name='creator-dashboard'),
    path('upload-url/', views.get_upload_url, name='creator-upload-url'),

    # ══════════════════════════════════════════════════════════════
    # CONTENT API
    # ══════════════════════════════════════════════════════════════
    path('content/', api_content.content_list, name='creator-content-list'),
    path('content/draft/', api_content.content_create_draft, name='creator-content-draft'),
    path('content/<uuid:content_id>/', api_content.content_detail, name='creator-content-detail'),
    path('content/<uuid:content_id>/update/', api_content.content_update, name='creator-content-update'),
    path('content/<uuid:content_id>/upload-thumbnail/', api_content.content_upload_thumbnail, name='creator-content-upload-thumbnail'),
    path('content/<uuid:content_id>/confirm-thumbnail/', api_content.content_confirm_thumbnail, name='creator-content-confirm-thumbnail'),
    path('content/<uuid:content_id>/upload-media/', api_content.content_upload_media, name='creator-content-upload-media'),
    path('content/<uuid:content_id>/confirm-media/', api_content.content_confirm_media, name='creator-content-confirm-media'),
    path('content/<uuid:content_id>/transcode/', api_content.content_transcode, name='creator-content-transcode'),
    path('content/<uuid:content_id>/publish/', api_content.content_publish, name='creator-content-publish'),
    path('content/<uuid:content_id>/unpublish/', api_content.content_unpublish, name='creator-content-unpublish'),
    path('content/<uuid:content_id>/archive/', api_content.content_archive, name='creator-content-archive'),

    # ══════════════════════════════════════════════════════════════
    # INSTRUCTORS API
    # ══════════════════════════════════════════════════════════════
    path('instructors/', api_instructors.instructor_list, name='creator-instructor-list'),
    path('instructors/create/', api_instructors.instructor_create, name='creator-instructor-create'),
    path('instructors/<uuid:instructor_id>/', api_instructors.instructor_detail, name='creator-instructor-detail'),
    path('instructors/<uuid:instructor_id>/update/', api_instructors.instructor_update, name='creator-instructor-update'),
    path('instructors/<uuid:instructor_id>/deactivate/', api_instructors.instructor_deactivate, name='creator-instructor-deactivate'),

    # Aliases: Vue frontend uses /experts/ — same handlers, different paths
    path('experts/', api_instructors.instructor_list, name='creator-expert-list'),
    path('experts/create/', api_instructors.instructor_create, name='creator-expert-create'),
    path('experts/<uuid:instructor_id>/', api_instructors.instructor_detail, name='creator-expert-detail'),
    path('experts/<uuid:instructor_id>/update/', api_instructors.instructor_update, name='creator-expert-update'),
    path('experts/<uuid:instructor_id>/deactivate/', api_instructors.instructor_deactivate, name='creator-expert-deactivate'),

    # ══════════════════════════════════════════════════════════════
    # CATEGORIES API
    # ══════════════════════════════════════════════════════════════
    path('categories/', api_categories.category_list, name='creator-category-list'),
    path('categories/create/', api_categories.category_create, name='creator-category-create'),
    path('categories/<uuid:category_id>/update/', api_categories.category_update, name='creator-category-update'),

    # ══════════════════════════════════════════════════════════════
    # SERIES API
    # ══════════════════════════════════════════════════════════════
    path('series/', api_series.series_list, name='creator-series-list'),
    path('series/create/', api_series.series_create, name='creator-series-create'),
    path('series/<uuid:series_id>/', api_series.series_detail, name='creator-series-detail'),
    path('series/<uuid:series_id>/update/', api_series.series_update, name='creator-series-update'),
    path('series/<uuid:series_id>/episodes/', api_series.series_add_episode, name='creator-series-add-episode'),
    path('series/<uuid:series_id>/episodes/<uuid:content_id>/', api_series.series_remove_episode, name='creator-series-remove-episode'),
    path('series/<uuid:series_id>/episodes/reorder/', api_series.series_reorder_episodes, name='creator-series-reorder'),
    path('series/<uuid:series_id>/upload-thumbnail/', api_series.series_upload_thumbnail, name='creator-series-upload-thumbnail'),
    path('series/<uuid:series_id>/confirm-thumbnail/', api_series.series_confirm_thumbnail, name='creator-series-confirm-thumbnail'),
    path('series/<uuid:series_id>/publish/', api_series.series_publish, name='creator-series-publish'),
    path('series/<uuid:series_id>/unpublish/', api_series.series_unpublish, name='creator-series-unpublish'),

    # ══════════════════════════════════════════════════════════════
    # LIVE SESSIONS API
    # ══════════════════════════════════════════════════════════════
    path('sessions/', api_sessions.session_list, name='creator-session-list'),
    path('sessions/create/', api_sessions.session_create, name='creator-session-create'),
    path('sessions/<uuid:session_id>/', api_sessions.session_detail, name='creator-session-detail'),
    path('sessions/<uuid:session_id>/update/', api_sessions.session_update, name='creator-session-update'),
    path('sessions/<uuid:session_id>/delete/', api_sessions.session_delete, name='creator-session-delete'),
    path('sessions/<uuid:session_id>/signup/', api_sessions.session_signup, name='creator-session-signup'),
    path('sessions/<uuid:session_id>/cancel-signup/', api_sessions.session_cancel_signup, name='creator-session-cancel-signup'),
]

