# bf-creator-bk

Standalone Django backend for the BetterFeel Creator Studio — content management, instructor profiles, series/playlists, and creator payouts via Stripe Connect.

## Architecture

This project **shares the same PostgreSQL database** as `betterbliss-auth`. It uses `managed = False` Django models to read/write existing tables without creating or modifying them.

### Apps

| App | Purpose | Tables |
|-----|---------|--------|
| `accounts` | Auth (login, register, token) | `auth_users` (shared) |
| `creator` | Content CRUD, instructors, categories, series | `content`, `experts`, `categories`, `content_series` (shared) |
| `payouts` | Stripe Connect, earnings, payout tracking | `creator_content_views`, `creator_payouts` |

### API Routes

```
/auth/login/           — Email/password login → token
/auth/register/        — Create educator account
/auth/me/              — Current user info
/auth/logout/          — Delete token

/api/creator/dashboard/    — Educator stats
/api/creator/content/*     — Content CRUD + upload pipeline
/api/creator/instructors/* — Instructor CRUD
/api/creator/categories/*  — Category CRUD
/api/creator/series/*      — Series/playlist CRUD
/api/creator/earnings/     — Creator earnings data
/api/creator/stripe/*      — Stripe Connect + webhook
```

## Quick Start

```bash
# 1. Setup
cp .env.example .env
# Edit .env with your database credentials

# 2. Install
pip install -r requirements.txt

# 3. Run
python manage.py runserver 8001
```

## Docker

```bash
docker-compose up --build
```

## Environment Variables

See `.env.example` for all required configuration.

## Frontend

The Vue.js Creator Studio frontend (`betterfeel-creator-ui/`) connects to this backend. No frontend changes are needed — the API paths are identical.
