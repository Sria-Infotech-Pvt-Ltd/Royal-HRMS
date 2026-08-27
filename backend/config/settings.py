import sys
import environ
from pathlib import Path
from datetime import timedelta
from celery.schedules import crontab

if sys.platform == 'win32':
    # Windows consoles default stdout/stderr to the legacy cp1252 codepage,
    # which can't encode characters like '→' or '—' used in log messages —
    # that crashes logging.StreamHandler.emit() with UnicodeEncodeError.
    for _stream in (sys.stdout, sys.stderr):
        if hasattr(_stream, 'reconfigure'):
            _stream.reconfigure(encoding='utf-8', errors='backslashreplace')

BASE_DIR = Path(__file__).resolve().parent.parent
ROOT_DIR = BASE_DIR.parent

env = environ.Env(DEBUG=(bool, False))
environ.Env.read_env(BASE_DIR / '.env')

SECRET_KEY = env('SECRET_KEY')
DEBUG = env('DEBUG')

# Field-level encryption for PII (bank account number, IFSC, PAN, UAN, Aadhaar
# name) — see core/encrypted_fields.py. FIELD_INDEX_HMAC_KEY is a separate key
# used only for deterministic blind-index hashing (exact-match lookups on
# encrypted fields, e.g. PAN duplicate detection) — never for encryption.
FIELD_ENCRYPTION_KEY = env('FIELD_ENCRYPTION_KEY')
FIELD_INDEX_HMAC_KEY = env('FIELD_INDEX_HMAC_KEY')
# Snapshotted separately from DEBUG, at the SAME .env-derived value, because
# Django's test runner force-overrides the live settings.DEBUG attribute to
# False for every `manage.py test` run — documented, intentional Django
# behaviour (so debug-only code paths, e.g. verbose error pages, never mask a
# production bug) — which makes DEBUG unusable as a "not a real production
# deployment" signal from inside a test. Checks that must still behave like
# local dev even under `manage.py test` — core.permissions.
# RequiresSecureTransport and services_face_matching's TLS precondition,
# both gating on an inherently HTTP-only local/test environment rather than
# genuinely wanting to enforce HTTPS in CI — read this instead of DEBUG.
IS_LOCAL_OR_TEST_ENV = DEBUG
ALLOWED_HOSTS = env.list('ALLOWED_HOSTS', default=[])

# ─── Multi-tenancy (django-tenants, PostgreSQL schema-per-company) ───────────
# SHARED_APPS live in the public schema — apps.tenants is the company
# registry (which schema each company maps to, which modules it has
# enabled); everything else is a TENANT_APP, meaning every company gets its
# own complete, isolated copy of those tables in its own schema. Isolation
# is enforced by which schema the DB connection is pointed at for a given
# request (see apps/tenants/middleware.py), not by an application-level
# `.filter(company=...)` added to every query — so none of the existing
# business logic (payroll, attendance, encryption, permissions, ...) needed
# to change for this. django.contrib.contenttypes/auth appear in BOTH lists
# per django-tenants' own convention: their tables need to exist in every
# tenant schema (TENANT_APPS, since AUTH_USER_MODEL is a tenant app) AND in
# the public schema (SHARED_APPS, for objects created before any tenant
# exists, e.g. during the very first `migrate_schemas --shared`).
# django.contrib.admin and rest_framework_simplejwt.token_blacklist are
# TENANT-ONLY (not shared): LogEntry and OutstandingToken/BlacklistedToken
# each have a FK to AUTH_USER_MODEL (accounts.User, a tenant app), which
# can't be satisfied in the public schema — each company gets its own admin
# log and token blacklist alongside its own users, which is the right
# behavior anyway (both are inherently per-company data).
SHARED_APPS = (
    'django_tenants',              # must be first
    'apps.tenants',

    'daphne',                      # first of the rest: replaces runserver with an ASGI-aware one
    'channels',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'cloudinary_storage',          # must come before staticfiles
    'django.contrib.staticfiles',
    'cloudinary',
    'rest_framework',
    'rest_framework_simplejwt',
    'corsheaders',
)

TENANT_APPS = (
    'django.contrib.admin',
    'rest_framework_simplejwt.token_blacklist',
    'django.contrib.contenttypes',
    'django.contrib.auth',

    'apps.accounts',
    'apps.branch',
    'apps.announcements',
    'apps.recruitment',
    'apps.hrms',
    'apps.attendance',
    'apps.assessments',
    'apps.notifications',
    'apps.dashboard',
    'apps.payroll',
    'apps.voice_commands',
)

INSTALLED_APPS = list(SHARED_APPS) + [app for app in TENANT_APPS if app not in SHARED_APPS]

TENANT_MODEL = 'tenants.Client'
TENANT_DOMAIN_MODEL = 'tenants.Domain'
DATABASE_ROUTERS = ('django_tenants.routers.TenantSyncRouter',)

MIDDLEWARE = [
    'corsheaders.middleware.CorsMiddleware',
    # Resolves which company schema this request runs against — must run
    # before anything else that touches the ORM (every app view included).
    'apps.tenants.middleware.TenantSchemaMiddleware',
    'django.middleware.security.SecurityMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
]

ROOT_URLCONF = 'config.urls'

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

WSGI_APPLICATION = 'config.wsgi.application'
ASGI_APPLICATION = 'config.asgi.application'

# ─── Database ────────────────────────────────────────────────────────────────
DATABASES = {
    'default': env.db('DATABASE_URL', default=f'sqlite:///{BASE_DIR}/db.sqlite3')
}
DATABASES['default']['CONN_MAX_AGE'] = env.int('DB_CONN_MAX_AGE', default=60)
# Neon (and any managed cloud Postgres) requires sslmode to be forwarded to
# psycopg2 — but a local PostgreSQL server (e.g. pgAdmin) almost never has
# SSL configured, so hardcoding 'require' here would break local setups.
# DB_SSL_MODE lets both be served by the same settings file: leave unset
# (defaults to 'require') for Neon/cloud, or set DB_SSL_MODE=disable in
# .env when pointing DATABASE_URL at a local server. Only applied as a
# default — a sslmode already present in DATABASE_URL's query string wins.
if DATABASES['default'].get('ENGINE') == 'django.db.backends.postgresql':
    DATABASES['default'].setdefault('OPTIONS', {})
    DATABASES['default']['OPTIONS'].setdefault('sslmode', env('DB_SSL_MODE', default='require'))
    # Multi-tenancy (see SHARED_APPS/TENANT_APPS above) is PostgreSQL-schema
    # based — django-tenants needs its own backend, a thin wrapper around
    # psycopg2 that sets the connection's search_path per request/tenant.
    # There is no SQLite equivalent: multi-tenancy requires Postgres.
    DATABASES['default']['ENGINE'] = 'django_tenants.postgresql_backend'

AUTH_USER_MODEL = 'accounts.User'

AUTH_PASSWORD_VALIDATORS = [
    {'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator'},
    {'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator'},
    {'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator'},
    {'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator'},
]

APPEND_SLASH = False

LANGUAGE_CODE = 'en-us'
TIME_ZONE = 'Asia/Kolkata'
USE_I18N = True
USE_TZ = True

STATIC_URL = '/static/'
STATIC_ROOT = BASE_DIR / 'staticfiles'
MEDIA_URL  = '/media/'
MEDIA_ROOT = BASE_DIR / 'media'
DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

# ─── Cloudinary (all FileField / ImageField uploads) ─────────────────────────
CLOUDINARY_STORAGE = {
    'CLOUD_NAME':             env('CLOUDINARY_CLOUD_NAME'),
    'API_KEY':                env('CLOUDINARY_API_KEY'),
    'API_SECRET':             env('CLOUDINARY_API_SECRET'),
    'SECURE':                 True,   # always serve over HTTPS
    'DELETE_CLOUDINARY_MEDIA': True,  # delete from Cloudinary when model instance is deleted
}

# ─── Sarvam AI (voice_commands LLM fallback + Hindi STT) ─────────────────────
# Server-side only — never exposed to the frontend, never a NEXT_PUBLIC_ var.
# Empty by default so a missing key fails soft (see apps.voice_commands.
# sarvam_client) rather than crashing settings import in environments that
# haven't added it yet.
SARVAM_API_KEY = env('SARVAM_API_KEY', default='')

# Django 5.1+ dropped the automatic DEFAULT_FILE_STORAGE/STATICFILES_STORAGE
# -> STORAGES translation shim (deprecated since 4.2) — STORAGES is now the
# only setting Django itself reads for FileField/ImageField.storage and
# collectstatic. Setting the legacy names as real module-level settings
# instead of (or alongside) STORAGES silently sent every upload to the
# built-in local-disk DefaultStorage rather than Cloudinary, since Django
# never applied them.
#
# Kept as their own names (not underscore-prefixed) — a prior version of
# this file believed Django 5.1 raises ImproperlyConfigured ("mutually
# exclusive") if both a legacy storage setting and STORAGES are defined at
# once, and hid them from Django as _DEFAULT_FILE_STORAGE_BACKEND/
# _STATICFILES_STORAGE_BACKEND for that reason. That's not true of the
# installed Django version (5.1.15) — grepping django/ turns up no such
# check, and django.contrib.staticfiles.checks.check_storages only
# requires STORAGES['staticfiles'] to exist, nothing about
# STATICFILES_STORAGE. It's also NOT true that Django computes
# settings.STATICFILES_STORAGE from STORAGES when the legacy name is left
# unset — Django 5.1 removed STATICFILES_STORAGE from its own internals
# entirely (no reference to it anywhere under django/), so reading it as a
# raw attribute when unset raises AttributeError, not a derived value. That
# was silently breaking collectstatic in production: django-cloudinary-
# storage's own collectstatic override (must come before staticfiles in
# INSTALLED_APPS below) still reads settings.STATICFILES_STORAGE directly —
# pre-STORAGES third-party code that hasn't caught up. Setting both here
# keeps STORAGES as the setting Django itself actually uses, while giving
# that older package's raw attribute read something to find.
DEFAULT_FILE_STORAGE = 'cloudinary_storage.storage.RawMediaCloudinaryStorage'
STATICFILES_STORAGE  = 'django.contrib.staticfiles.storage.StaticFilesStorage'

STORAGES = {
    'default': {
        'BACKEND': DEFAULT_FILE_STORAGE,
    },
    'staticfiles': {
        'BACKEND': STATICFILES_STORAGE,
    },
}

# ─── Cache ───────────────────────────────────────────────────────────────────
# rediss:// (SSL) requires ssl_cert_reqs; append it when the URL uses that scheme.
# redis-py only accepts the lowercase strings "none"/"optional"/"required" here,
# not the ssl.CERT_REQUIRED constant name.
def _with_ssl_cert_reqs(url: str) -> str:
    if url.startswith('rediss://') and 'ssl_cert_reqs' not in url:
        sep = '&' if '?' in url else '?'
        url = f'{url}{sep}ssl_cert_reqs=required'
    return url

_REDIS_URL = _with_ssl_cert_reqs(env('REDIS_URL', default=''))

if _REDIS_URL:
    CACHES = {
        'default': {
            'BACKEND': 'django_redis.cache.RedisCache',
            'LOCATION': _REDIS_URL,
            'OPTIONS': {
                'CLIENT_CLASS': 'django_redis.client.DefaultClient',
                'SOCKET_CONNECT_TIMEOUT': 5,
                'SOCKET_TIMEOUT': 5,
                # Every custom cache service in core/cache_service.py already
                # wraps cache.get/set in try/except and falls back to the DB
                # on failure — cache is meant to be an optimization, never a
                # hard dependency. DRF's built-in throttle classes don't
                # follow that pattern; they hit the cache raw, so without
                # this a Redis outage/misconfiguration 500s every throttled
                # endpoint (e.g. login) instead of just degrading (throttling
                # silently no-ops) like the rest of the app already does.
                'IGNORE_EXCEPTIONS': True,
            },
            'KEY_PREFIX': 'hrms',
            # Prepends the active tenant's schema name to every cache key —
            # see core/cache_keys.py. Without this, this shared Redis
            # instance would serve one company's cached data (KPIs, leave
            # policy, branch/department lists, etc.) to every other company.
            'KEY_FUNCTION': 'core.cache_keys.tenant_aware_key_func',
        }
    }
    # Logs a WARNING (via the django_redis.cache logger) each time
    # IGNORE_EXCEPTIONS above swallows a Redis error, so an outage stays
    # visible in the logs instead of failing completely silently.
    DJANGO_REDIS_LOG_IGNORED_EXCEPTIONS = True
else:
    CACHES = {
        'default': {
            'BACKEND': 'django.core.cache.backends.locmem.LocMemCache',
            # Same cross-tenant reasoning as the Redis KEY_FUNCTION above —
            # LocMemCache is a single in-process dict shared by every
            # request this worker process handles, tenant or not.
            'KEY_FUNCTION': 'core.cache_keys.tenant_aware_key_func',
        }
    }

# ─── Channels (WebSocket notifications) ──────────────────────────────────────
# Mirrors the CACHES fallback above: real Redis when REDIS_URL is configured,
# otherwise the in-memory layer. Like LocMemCache, that only works within a
# single process — fine for `runserver`, not multiple gunicorn/daphne workers
# in production, where REDIS_URL must be set.
if _REDIS_URL:
    CHANNEL_LAYERS = {
        'default': {
            'BACKEND': 'channels_redis.core.RedisChannelLayer',
            'CONFIG': {'hosts': [_REDIS_URL]},
        }
    }
else:
    CHANNEL_LAYERS = {
        'default': {'BACKEND': 'channels.layers.InMemoryChannelLayer'},
    }

# ─── Celery ──────────────────────────────────────────────────────────────────
# Broker: reuse the same Redis URL used by the cache layer.
def _celery_redis_url(default: str) -> str:
    return _with_ssl_cert_reqs(env('REDIS_URL', default=default))

if _REDIS_URL:
    CELERY_BROKER_URL        = _celery_redis_url('redis://localhost:6379/1')
    CELERY_RESULT_BACKEND    = _celery_redis_url('redis://localhost:6379/1')
    CELERY_TASK_ALWAYS_EAGER = False
else:
    # No Redis configured at all (e.g. local dev with no Docker/WSL/native
    # Redis) — mirrors the CACHES/CHANNEL_LAYERS fallback above, which this
    # block previously didn't: it used to default to 'redis://localhost:6379/1'
    # unconditionally, so every .apply_async()/.delay() call (e.g.
    # apps/recruitment/views.py's interview-scheduled email dispatch) tried
    # and failed to reach a broker that was never configured, producing a
    # kombu.exceptions.OperationalError on every call. ALWAYS_EAGER runs
    # tasks synchronously in-process instead — safe here since no
    # @shared_task in this codebase depends on true async/fire-and-forget
    # semantics for correctness (they're all fetch-record-and-send-email /
    # compute-and-save style). EAGER_PROPAGATES=True keeps failures visible
    # to the same try/except that already wraps every apply_async() call
    # site, matching today's real-broker error-logging behavior.
    CELERY_BROKER_URL            = 'memory://'
    CELERY_RESULT_BACKEND        = 'cache+memory://'
    CELERY_TASK_ALWAYS_EAGER     = True
    CELERY_TASK_EAGER_PROPAGATES = True
CELERY_TIMEZONE          = 'Asia/Kolkata'
CELERY_TASK_TRACK_STARTED = True
CELERY_TASK_SERIALIZER   = 'json'
CELERY_RESULT_SERIALIZER = 'json'
CELERY_ACCEPT_CONTENT    = ['json']

CELERY_BROKER_CONNECTION_RETRY_ON_STARTUP = True

# Caps how long a single broker connection attempt can hang when Redis is
# unreachable. Without this, a dead/unreachable broker leaves request-path
# task dispatch (.delay()/.apply_async() calls made during a view) blocked
# on OS-level TCP timeouts far longer than any frontend request timeout.
CELERY_BROKER_TRANSPORT_OPTIONS = {
    'socket_connect_timeout': 0.2,
    'socket_timeout': 0.2,
}

# broker_connection_max_retries governs *acquiring* a broker connection
# (separate from the per-call `retry=` flag, which only governs retrying
# the publish once a connection exists) and backs off with a 1s sleep
# between attempts by default — that backoff, not the socket timeout
# above, is what actually blocked request-path dispatch calls for several
# seconds when the broker was unreachable. 0 is treated as falsy by
# Kombu's retry_over_time and falls back to its default retry count, so
# use 1 (the smallest value that actually takes effect: one retry, one
# 1s backoff sleep) to bound a dead broker to a single retry.
CELERY_BROKER_CONNECTION_MAX_RETRIES = 1

CELERY_BEAT_SCHEDULE = {
    # Runs every 5 minutes — detects employees past shift_end + grace with no clock-out.
    'check-missing-clockouts': {
        'task':     'apps.attendance.tasks.check_missing_clockouts',
        'schedule': 300.0,  # seconds
    },
    # Runs every 5 minutes — flips any company provisioning stuck at
    # 'pending' (worker died mid-task) to 'failed' so the platform-admin
    # UI doesn't show "Provisioning..." forever with no recovery path.
    'sweep-stale-provisioning': {
        'task':     'apps.tenants.tasks.sweep_stale_provisioning',
        'schedule': 300.0,  # seconds
    },
    # Runs once daily at 09:00 IST — fires absence alerts for employees absent N+ consecutive days.
    'check-absence-alerts': {
        'task':     'apps.attendance.tasks.check_absence_alerts',
        'schedule': crontab(hour=9, minute=0),
    },
    # Runs daily at 00:05 IST — sends birthday wishes (email + in-app
    # notifications) to employees. Offset 5 min past midnight rather than
    # exactly 00:00 so it doesn't collide with other midnight-triggered jobs.
    'send-birthday-wishes': {
        'task':     'apps.hrms.tasks.send_birthday_wishes',
        'schedule': crontab(hour=0, minute=5),
    },
    # Runs once a year on 1st Jan at 00:01 IST — resets leave balances for the new year
    # and applies carry-forward from the previous year.
    'reset-annual-leave-balances': {
        'task':     'apps.hrms.tasks.reset_annual_leave_balances',
        'schedule': crontab(hour=0, minute=1, day_of_month=1, month_of_year=1),
    },
    # Runs daily at 10:00 IST — nudges managers who haven't approved payroll
    # attendance within 24 hours of the cycle being created.
    'send-payroll-approval-reminders': {
        'task':     'apps.payroll.tasks.send_payroll_approval_reminders',
        'schedule': crontab(hour=10, minute=0),
    },
}

# ─── DRF ─────────────────────────────────────────────────────────────────────
REST_FRAMEWORK = {
    'DEFAULT_AUTHENTICATION_CLASSES': (
        'apps.accounts.authentication.CookieJWTAuthentication',
    ),
    'DEFAULT_PERMISSION_CLASSES': (
        'rest_framework.permissions.IsAuthenticated',
    ),
    'DEFAULT_THROTTLE_CLASSES': [
        'rest_framework.throttling.AnonRateThrottle',
        'rest_framework.throttling.UserRateThrottle',
    ],
    'DEFAULT_THROTTLE_RATES': {
        'anon':                 '300/hour',
        'user':                 '3000/hour',
        'login':                '20/hour',
        'forgot_password':      '5/hour',
        'otp_verify':           '10/hour',
        'platform_admin_login': '20/hour',
        'platform_admin_forgot_password': '5/hour',
        'platform_admin_otp_verify':      '10/hour',
    },
    'EXCEPTION_HANDLER': 'config.exceptions.custom_exception_handler',
}

# ─── JWT ─────────────────────────────────────────────────────────────────────
SIMPLE_JWT = {
    'ACCESS_TOKEN_LIFETIME': timedelta(minutes=15),
    'REFRESH_TOKEN_LIFETIME': timedelta(days=7),
    'ROTATE_REFRESH_TOKENS': True,
    'BLACKLIST_AFTER_ROTATION': True,
    'AUTH_HEADER_TYPES': ('Bearer',),
}

# ─── Email ───────────────────────────────────────────────────────────────────
EMAIL_BACKEND      = (
    'django.core.mail.backends.console.EmailBackend'
    if DEBUG
    else 'django.core.mail.backends.smtp.EmailBackend'
)
DEFAULT_FROM_EMAIL = env('DEFAULT_FROM_EMAIL', default='Royal Staffing HRMS <noreply@hrms.com>')

OTP_EXPIRY_MINUTES = 10
OTP_MAX_ATTEMPTS = 5
LOGIN_MAX_ATTEMPTS = 5
LOGIN_LOCKOUT_MINUTES = 30

# The one shared frontend URL every company signs in through (no per-company
# subdomains) — used to build a clickable login link in the provisioning
# welcome email. Must NOT have a trailing slash (see apps.tenants.utils
# send_company_provisioned_email, which appends '/login').
FRONTEND_URL = env('FRONTEND_URL', default='http://localhost:3000').rstrip('/')

CORS_ALLOWED_ORIGINS = env.list(
    'CORS_ALLOWED_ORIGINS',
    default=['http://localhost:3000'],
)
CORS_ALLOW_CREDENTIALS = True
CORS_PREFLIGHT_MAX_AGE = 86400

# Production origins (e.g. the deployed frontend/admin domain) must be supplied via env.
CSRF_TRUSTED_ORIGINS = env.list('CSRF_TRUSTED_ORIGINS', default=[])

# ─── CSRF: deliberate reliance on SameSite, not a token check ────────────────
# DRF's APIView.as_view() always disables Django's CsrfViewMiddleware for API
# views; DRF only re-enables a CSRF check itself when SessionAuthentication is
# the authenticating class (SessionAuthentication.enforce_csrf()). This app's
# DEFAULT_AUTHENTICATION_CLASSES is apps.accounts.authentication.CookieJWTAuthentication
# (see below), which reads the JWT straight from the httpOnly royal_access_token
# cookie — so that CSRF check path never runs, and no separate CSRF token is
# issued or verified anywhere in this stack.
#
# The only thing preventing a cross-site page from riding that cookie into a
# state-changing request is SameSite=Lax on royal_access_token/royal_refresh_token
# (set in accounts/views.py's LoginView/TokenRefreshAPIView) — every modern
# browser withholds a Lax cookie from cross-site POST/PUT/PATCH/DELETE and from
# any cross-site fetch/XHR regardless of method, which covers this API (JSON,
# no state-changing GETs). This is an accepted, explicit design choice, not an
# oversight — revisit with a real double-submit CSRF token if a client that
# doesn't honor SameSite ever needs to be supported.

if DEBUG:
    # Dev-only: allow any localhost port (Flutter web) and any 192.168.x.x port
    # (local network devices). Not active in production — CORS_ALLOWED_ORIGINS only.
    CORS_ALLOWED_ORIGIN_REGEXES = [
        r'^http://localhost(:\d+)?$',
        r'^http://192\.168\.\d+\.\d+(:\d+)?$',
    ]
    # Allow Django admin CSRF from localhost (any port) in development.
    CSRF_TRUSTED_ORIGINS += [
        'http://localhost:8000',
        'http://localhost:8008',
        'http://127.0.0.1:8000',
        'http://127.0.0.1:8008',
    ]

# ─── Upload limits ────────────────────────────────────────────────────────────
DATA_UPLOAD_MAX_MEMORY_SIZE = 5 * 1024 * 1024   # 5 MB JSON body
FILE_UPLOAD_MAX_MEMORY_SIZE = 10 * 1024 * 1024  # 10 MB files

# ─── Security (production only) ───────────────────────────────────────────────
if not DEBUG:
    SECURE_SSL_REDIRECT             = True
    SECURE_HSTS_SECONDS             = 31536000
    SECURE_HSTS_INCLUDE_SUBDOMAINS  = True
    SECURE_HSTS_PRELOAD             = True
    SESSION_COOKIE_SECURE           = True
    CSRF_COOKIE_SECURE              = True
    SECURE_BROWSER_XSS_FILTER       = True
    SECURE_CONTENT_TYPE_NOSNIFF     = True
    X_FRAME_OPTIONS                 = 'DENY'

# ─── Logging ─────────────────────────────────────────────────────────────────
LOGS_DIR = BASE_DIR / 'logs'
LOGS_DIR.mkdir(exist_ok=True)

# `manage.py test` runs exercise real code paths (handle_transcript,
# sarvam_client, audit._record, ...) that log exactly like production
# traffic, and until now those entries landed in the SAME files real dev/
# production usage does — indistinguishable from genuine events without
# reading each test's mocks. Confirmed directly: every "Sarvam STT
# succeeded" line in logs/voice_commands.log, across every date, turned out
# on inspection to be test_sarvam_client.py's mocked fixture, not a real
# transcription — this made that file useless as a real-data source for
# calibrating anything (see voice_review_report's own docstring on why real
# data matters here). Test runs get their own subdirectory instead — same
# handlers/rotation/formatting, just never the same files.
RUNNING_TESTS = len(sys.argv) > 1 and sys.argv[1] == 'test'
_LOG_DIR = (LOGS_DIR / 'test') if RUNNING_TESTS else LOGS_DIR
_LOG_DIR.mkdir(exist_ok=True)

LOGGING = {
    'version': 1,
    'disable_existing_loggers': False,
    'formatters': {
        'verbose': {
            'format': '[{asctime}] {levelname} {name} — {message}',
            'style': '{',
        },
    },
    'handlers': {
        'auth_file': {
            'level': 'INFO',
            'class': 'logging.handlers.RotatingFileHandler',
            'filename': _LOG_DIR / 'auth.log',
            'maxBytes': 5 * 1024 * 1024,  # 5 MB per file
            'backupCount': 5,
            'formatter': 'verbose',
            'encoding': 'utf-8',
        },
        'error_file': {
            'level': 'WARNING',
            'class': 'logging.handlers.RotatingFileHandler',
            'filename': _LOG_DIR / 'errors.log',
            'maxBytes': 5 * 1024 * 1024,  # 5 MB per file
            'backupCount': 5,
            'formatter': 'verbose',
            'encoding': 'utf-8',
        },
        'voice_commands_file': {
            'level': 'INFO',
            'class': 'logging.handlers.RotatingFileHandler',
            'filename': _LOG_DIR / 'voice_commands.log',
            'maxBytes': 5 * 1024 * 1024,  # 5 MB per file
            'backupCount': 5,
            'formatter': 'verbose',
            'encoding': 'utf-8',
        },
        'console': {
            'class': 'logging.StreamHandler',
            'formatter': 'verbose',
        },
    },
    'loggers': {
        'accounts': {
            'handlers': ['auth_file', 'console'],
            'level': 'INFO',
            'propagate': False,
        },
        'django': {
            'handlers': ['error_file', 'console'],
            'level': 'WARNING',
            'propagate': False,
        },
        # Keyed 'apps.voice_commands' (not a bare 'voice_commands' string) —
        # every module in this app logs via logging.getLogger(__name__), which
        # resolves to 'apps.voice_commands.<module>' (e.g.
        # 'apps.voice_commands.conversation'). Python's logging hierarchy walks
        # up dotted parents, so a logger registered here as 'apps.voice_commands'
        # catches every submodule's calls via propagation. A bare 'voice_commands'
        # key (mirroring the 'accounts' entry above literally) would NOT match
        # that hierarchy and would silently catch nothing.
        'apps.voice_commands': {
            'handlers': ['voice_commands_file', 'console'],
            'level': 'INFO',
            'propagate': False,
        },
    },
    'root': {
        'handlers': ['error_file', 'console'],
        'level': 'WARNING',
    },
}
