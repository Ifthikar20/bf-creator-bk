"""
BetterFeel Creator Backend — Django Settings.

Standalone Django project for creator content management, payouts, and Stripe.
Shares the same PostgreSQL database as betterbliss-auth.
"""

import os
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

BASE_DIR = Path(__file__).resolve().parent.parent

# =============================================================================
# CORE
# =============================================================================

SECRET_KEY = os.getenv('SECRET_KEY', 'django-insecure-change-me-in-production')
DEBUG = os.getenv('ENVIRONMENT', 'development') == 'development'
ENVIRONMENT = os.getenv('ENVIRONMENT', 'development')

ALLOWED_HOSTS = ['*'] if DEBUG else [
    'api.betterandbliss.com',
    'creator.betterandbliss.com',
    '*.amplifyapp.com',
    'localhost',
]

# =============================================================================
# APPS
# =============================================================================

INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',

    # Third-party
    'rest_framework',
    'rest_framework.authtoken',
    'corsheaders',

    # Creator apps
    'accounts',
    'creator',
    'payouts',
]

MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'corsheaders.middleware.CorsMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
]

ROOT_URLCONF = 'creator_project.urls'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.debug',
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
            ],
        },
    },
]

WSGI_APPLICATION = 'creator_project.wsgi.application'

# =============================================================================
# AUTH — Uses the same User table as betterbliss-auth
# =============================================================================

AUTH_USER_MODEL = 'accounts.CreatorUser'

# =============================================================================
# DATABASE — Same PostgreSQL as betterbliss-auth
# =============================================================================

DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.postgresql',
        'NAME': os.getenv('DB_NAME', 'betterbliss'),
        'USER': os.getenv('DB_USERNAME', 'betterbliss_user'),
        'PASSWORD': os.getenv('DB_PASSWORD', ''),
        'HOST': os.getenv('DB_HOST', 'localhost'),
        'PORT': os.getenv('DB_PORT', '5432'),
        'OPTIONS': {
            'sslmode': os.getenv('DB_SSL_MODE', 'require'),
        },
        'CONN_MAX_AGE': 600,
    }
}

# =============================================================================
# REST FRAMEWORK
# =============================================================================

REST_FRAMEWORK = {
    'DEFAULT_AUTHENTICATION_CLASSES': [
        'accounts.token_auth.ExpiringTokenAuthentication',
    ],
    'DEFAULT_PERMISSION_CLASSES': [
        'rest_framework.permissions.IsAuthenticated',
    ],
    'DEFAULT_RENDERER_CLASSES': [
        'rest_framework.renderers.JSONRenderer',
    ],
    'DEFAULT_THROTTLE_CLASSES': [
        'rest_framework.throttling.AnonRateThrottle',
        'rest_framework.throttling.UserRateThrottle',
    ],
    'DEFAULT_THROTTLE_RATES': {
        'anon': '30/minute',
        'user': '120/minute',
    },
}

TOKEN_EXPIRY_DAYS = int(os.getenv('TOKEN_EXPIRY_DAYS', '7'))

# =============================================================================
# PASSWORD HASHERS — Must match betterbliss-auth
# =============================================================================

PASSWORD_HASHERS = [
    'django.contrib.auth.hashers.Argon2PasswordHasher',
    'django.contrib.auth.hashers.PBKDF2PasswordHasher',
    'django.contrib.auth.hashers.PBKDF2SHA1PasswordHasher',
]

AUTH_PASSWORD_VALIDATORS = [
    {'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator',
     'OPTIONS': {'min_length': 8}},
    {'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator'},
    {'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator'},
]

# =============================================================================
# CORS
# =============================================================================

_cors_env = os.getenv('CORS_ALLOWED_ORIGINS', '')
CORS_ALLOWED_ORIGINS = [o.strip() for o in _cors_env.split(',') if o.strip()] if _cors_env else []

if DEBUG:
    CORS_ALLOWED_ORIGINS += [
        'http://localhost:5173',
        'http://127.0.0.1:5173',
        'http://localhost:3000',
        'http://127.0.0.1:3000',
    ]

CORS_ALLOW_CREDENTIALS = True
CORS_ALLOW_HEADERS = [
    'accept', 'accept-encoding', 'authorization', 'content-type',
    'dnt', 'origin', 'user-agent', 'x-csrftoken', 'x-requested-with',
]

# =============================================================================
# AWS (S3 / CloudFront)
# =============================================================================

AWS_REGION = os.getenv('AWS_REGION', 'us-east-1')
AWS_ACCESS_KEY_ID = os.getenv('AWS_ACCESS_KEY_ID')
AWS_SECRET_ACCESS_KEY = os.getenv('AWS_SECRET_ACCESS_KEY')
VIDEO_BUCKET_NAME = os.getenv('VIDEO_BUCKET_NAME', 'betterbliss-videos-production')
CLOUDFRONT_DOMAIN = os.getenv('CLOUDFRONT_DOMAIN', 'd2f89dacgjld08.cloudfront.net')

# =============================================================================
# STRIPE (Creator payouts via Stripe Connect)
# =============================================================================

STRIPE_SECRET_KEY = os.getenv('STRIPE_SECRET_KEY', '')
STRIPE_WEBHOOK_SECRET = os.getenv('STRIPE_WEBHOOK_SECRET', '')
STRIPE_CONNECT_RETURN_URL = os.getenv(
    'STRIPE_CONNECT_RETURN_URL',
    'https://creator.betterandbliss.com/earnings',
)

# =============================================================================
# SECURITY
# =============================================================================

SECURE_CONTENT_TYPE_NOSNIFF = True
SECURE_BROWSER_XSS_FILTER = True
X_FRAME_OPTIONS = 'DENY'
SECURE_REFERRER_POLICY = 'strict-origin-when-cross-origin'

SESSION_ENGINE = 'django.contrib.sessions.backends.db'
SESSION_COOKIE_HTTPONLY = True
SESSION_COOKIE_SECURE = ENVIRONMENT == 'production'
CSRF_COOKIE_HTTPONLY = True
CSRF_COOKIE_SECURE = ENVIRONMENT == 'production'

# =============================================================================
# STATIC & MISC
# =============================================================================

STATIC_URL = '/static/'
STATIC_ROOT = BASE_DIR / 'staticfiles'
DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

# =============================================================================
# LOGGING
# =============================================================================

LOGGING = {
    'version': 1,
    'disable_existing_loggers': False,
    'formatters': {
        'verbose': {
            'format': '{asctime} {name} {levelname} {message}',
            'style': '{',
        },
    },
    'handlers': {
        'console': {
            'class': 'logging.StreamHandler',
            'formatter': 'verbose',
        },
    },
    'root': {
        'handlers': ['console'],
        'level': 'INFO',
    },
    'loggers': {
        'django': {
            'handlers': ['console'],
            'level': 'WARNING',
            'propagate': False,
        },
        'creator': {
            'handlers': ['console'],
            'level': 'INFO',
            'propagate': False,
        },
        'payouts': {
            'handlers': ['console'],
            'level': 'INFO',
            'propagate': False,
        },
    },
}
