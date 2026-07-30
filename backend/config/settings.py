import environ
from pathlib import Path
from datetime import timedelta
from celery.schedules import crontab

BASE_DIR = Path(__file__).resolve().parent.parent
ROOT_DIR = BASE_DIR.parent

env = environ.Env(DEBUG=(bool, False))
environ.Env.read_env(BASE_DIR / '.env')

SECRET_KEY = env('SECRET_KEY')
DEBUG = env('DEBUG')
ALLOWED_HOSTS = env.list('ALLOWED_HOSTS', default=[])

INSTALLED_APPS = [
    'daphne',                      # first: replaces runserver with an ASGI-aware one
    'channels',
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'cloudinary_storage',          # must come before staticfiles
    'django.contrib.staticfiles',
    'cloudinary',
    'rest_framework',
    'rest_framework_simplejwt',
    'rest_framework_simplejwt.token_blacklist',
    'corsheaders',
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
]

MIDDLEWARE = [
    'corsheaders.middleware.CorsMiddleware',
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
# Neon (and any SSL Postgres) requires sslmode to be forwarded to psycopg2
if DATABASES['default'].get('ENGINE') == 'django.db.backends.postgresql':
    DATABASES['default'].setdefault('OPTIONS', {})
    DATABASES['default']['OPTIONS'].setdefault('sslmode', 'require')

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
# RawMediaCloudinaryStorage handles PDFs, DOCs, XLS, images — every file type
DEFAULT_FILE_STORAGE = 'cloudinary_storage.storage.RawMediaCloudinaryStorage'

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
            },
            'KEY_PREFIX': 'hrms',
        }
    }
else:
    CACHES = {
        'default': {
            'BACKEND': 'django.core.cache.backends.locmem.LocMemCache',
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
# Falls back to localhost Redis in development when REDIS_URL is not set.
def _celery_redis_url(default: str) -> str:
    return _with_ssl_cert_reqs(env('REDIS_URL', default=default))

CELERY_BROKER_URL        = _celery_redis_url('redis://localhost:6379/1')
CELERY_RESULT_BACKEND    = _celery_redis_url('redis://localhost:6379/1')
CELERY_TIMEZONE          = 'Asia/Kolkata'
CELERY_TASK_TRACK_STARTED = True
CELERY_TASK_SERIALIZER   = 'json'
CELERY_RESULT_SERIALIZER = 'json'
CELERY_ACCEPT_CONTENT    = ['json']

CELERY_BROKER_CONNECTION_RETRY_ON_STARTUP = True

from celery.schedules import crontab

CELERY_BEAT_SCHEDULE = {
    # Runs every 5 minutes — detects employees past shift_end + grace with no clock-out.
    'check-missing-clockouts': {
        'task':     'apps.attendance.tasks.check_missing_clockouts',
        'schedule': 300.0,  # seconds
    },
    # Runs once daily at 09:00 IST — fires absence alerts for employees absent N+ consecutive days.
    'check-absence-alerts': {
        'task':     'apps.attendance.tasks.check_absence_alerts',
        'schedule': crontab(hour=9, minute=0),
    },
    # Runs daily at 9:00 AM IST — sends birthday wish emails to employees.
    'send-birthday-wishes': {
        'task':     'apps.hrms.tasks.send_birthday_wishes',
        'schedule': crontab(hour=9, minute=0),
    },
    # Runs once a year on 1st Jan at 00:01 IST — resets leave balances for the new year
    # and applies carry-forward from the previous year.
    'reset-annual-leave-balances': {
        'task':     'apps.hrms.tasks.reset_annual_leave_balances',
        'schedule': crontab(hour=0, minute=1, day_of_month=1, month_of_year=1),
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
        'anon':            '300/hour',
        'user':            '3000/hour',
        'login':           '20/hour',
        'forgot_password': '5/hour',
        'otp_verify':      '10/hour',
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

CORS_ALLOWED_ORIGINS = env.list(
    'CORS_ALLOWED_ORIGINS',
    default=['http://localhost:3000'],
)
CORS_ALLOW_CREDENTIALS = True
CORS_PREFLIGHT_MAX_AGE = 86400

# Production origins (e.g. the deployed frontend/admin domain) must be supplied via env.
CSRF_TRUSTED_ORIGINS = env.list('CSRF_TRUSTED_ORIGINS', default=[])

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
            'filename': LOGS_DIR / 'auth.log',
            'maxBytes': 5 * 1024 * 1024,  # 5 MB per file
            'backupCount': 5,
            'formatter': 'verbose',
        },
        'error_file': {
            'level': 'WARNING',
            'class': 'logging.handlers.RotatingFileHandler',
            'filename': LOGS_DIR / 'errors.log',
            'maxBytes': 5 * 1024 * 1024,  # 5 MB per file
            'backupCount': 5,
            'formatter': 'verbose',
        },
        'voice_commands_file': {
            'level': 'INFO',
            'class': 'logging.handlers.RotatingFileHandler',
            'filename': LOGS_DIR / 'voice_commands.log',
            'maxBytes': 5 * 1024 * 1024,  # 5 MB per file
            'backupCount': 5,
            'formatter': 'verbose',
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
