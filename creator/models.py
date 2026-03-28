"""
Creator app models — maps to existing database tables.

All models that map to tables owned by betterbliss-auth use managed=False.
BlogPost and ContentReview are managed=True (new tables for this project).
"""

import uuid
from django.db import models
from django.conf import settings


# =============================================================================
# CATEGORY — maps to existing `categories` table
# =============================================================================

class Category(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4)
    name = models.CharField(max_length=255)
    slug = models.SlugField(max_length=255, unique=True)
    description = models.TextField(null=True, blank=True)
    icon_url = models.TextField(null=True, blank=True)
    sort_order = models.IntegerField(default=0)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'categories'
        managed = False
        ordering = ['sort_order']
        verbose_name_plural = 'Categories'

    def __str__(self):
        return self.name


# =============================================================================
# EXPERT — maps to existing `experts` table
# =============================================================================

class Expert(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4)
    name = models.CharField(max_length=255)
    slug = models.SlugField(max_length=255, unique=True)
    title = models.CharField(max_length=255, null=True, blank=True)
    bio = models.TextField(null=True, blank=True)
    avatar_url = models.TextField(null=True, blank=True)
    background_image_url = models.TextField(null=True, blank=True)
    specialties = models.TextField(null=True, blank=True)
    is_featured = models.BooleanField(default=False, db_column='featured')
    fun_fact = models.TextField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='expert_profile',
    )

    class Meta:
        db_table = 'experts'
        managed = False
        ordering = ['-is_featured', 'name']

    def __str__(self):
        return self.name


# =============================================================================
# CONTENT STATUS
# =============================================================================

class ContentStatus(models.TextChoices):
    DRAFT = 'draft', 'Draft'
    PENDING_REVIEW = 'pending_review', 'Pending Review'
    APPROVED = 'approved', 'Approved'
    REJECTED = 'rejected', 'Rejected'
    PUBLISHED = 'published', 'Published'
    ARCHIVED = 'archived', 'Archived'


# =============================================================================
# CONTENT — maps to existing `content` table
# =============================================================================

class Content(models.Model):
    class ContentType(models.TextChoices):
        VIDEO = 'video', 'Video'
        AUDIO = 'audio', 'Audio'
        ARTICLE = 'article', 'Article'

    id = models.UUIDField(primary_key=True, default=uuid.uuid4)
    title = models.CharField(max_length=500)
    description = models.TextField(null=True, blank=True)
    content_type = models.CharField(max_length=50, choices=ContentType.choices)
    category = models.ForeignKey(
        Category, on_delete=models.SET_NULL, null=True, blank=True,
        db_column='category_id',
    )
    expert = models.ForeignKey(
        Expert, on_delete=models.SET_NULL, null=True, blank=True,
        db_column='expert_id',
    )
    thumbnail_s3_key = models.TextField(null=True, blank=True)
    media_s3_key = models.TextField(null=True, blank=True)
    hls_s3_key = models.TextField(null=True, blank=True)
    duration_seconds = models.IntegerField(null=True, blank=True)
    is_premium = models.BooleanField(default=False)
    is_published = models.BooleanField(default=True)
    tags = models.TextField(null=True, blank=True)
    view_count = models.IntegerField(default=0)
    series_id = models.UUIDField(null=True, blank=True)
    episode_number = models.IntegerField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    # Workflow fields
    status = models.CharField(
        max_length=20,
        choices=ContentStatus.choices,
        default=ContentStatus.DRAFT,
        db_index=True,
    )
    submitted_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='submitted_content',
    )
    reviewed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='reviewed_content',
    )
    review_notes = models.TextField(null=True, blank=True)
    reviewed_at = models.DateTimeField(null=True, blank=True)
    submitted_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = 'content'
        managed = False
        ordering = ['-created_at']

    def __str__(self):
        return f'{self.title} [{self.status}]'

    def get_status_display(self):
        return dict(ContentStatus.choices).get(self.status, self.status)


# =============================================================================
# BLOG POST — managed=True (this project owns this table)
# =============================================================================

class BlogPost(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    title = models.CharField(max_length=500)
    slug = models.SlugField(max_length=500, unique=True)
    body = models.TextField()
    excerpt = models.TextField(max_length=500, blank=True, default='')
    cover_image_url = models.TextField(null=True, blank=True)
    tags = models.TextField(null=True, blank=True)
    category = models.ForeignKey(
        Category, on_delete=models.SET_NULL, null=True, blank=True,
    )

    status = models.CharField(
        max_length=20,
        choices=ContentStatus.choices,
        default=ContentStatus.DRAFT,
        db_index=True,
    )
    author = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='blog_posts',
    )
    reviewed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='reviewed_blog_posts',
    )
    review_notes = models.TextField(null=True, blank=True)
    reviewed_at = models.DateTimeField(null=True, blank=True)

    view_count = models.IntegerField(default=0)
    read_time_minutes = models.IntegerField(default=5)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    published_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = 'blog_posts'
        managed = False
        ordering = ['-created_at']

    def __str__(self):
        return f'{self.title} [{self.status}]'

    def get_status_display(self):
        return dict(ContentStatus.choices).get(self.status, self.status)


# =============================================================================
# CONTENT REVIEW — audit trail
# =============================================================================

class ContentReview(models.Model):
    class ReviewAction(models.TextChoices):
        SUBMITTED = 'submitted', 'Submitted for Review'
        APPROVED = 'approved', 'Approved'
        REJECTED = 'rejected', 'Rejected'
        REVISION_REQUESTED = 'revision_requested', 'Revision Requested'
        PUBLISHED = 'published', 'Published'

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    content = models.ForeignKey(
        Content, on_delete=models.CASCADE,
        null=True, blank=True,
        related_name='reviews',
    )
    blog_post = models.ForeignKey(
        BlogPost, on_delete=models.CASCADE,
        null=True, blank=True,
        related_name='reviews',
    )
    action = models.CharField(max_length=20, choices=ReviewAction.choices)
    reviewer = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        related_name='content_reviews',
    )
    notes = models.TextField(blank=True, default='')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'content_reviews'
        managed = False
        ordering = ['-created_at']

    def __str__(self):
        target = self.content or self.blog_post
        return f'{self.action} — {target} by {self.reviewer}'
