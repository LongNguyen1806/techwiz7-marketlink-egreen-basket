import os
from datetime import timedelta
from pathlib import Path
from corsheaders.defaults import default_headers
from django.core.exceptions import ImproperlyConfigured
from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent.parent
load_dotenv(BASE_DIR / ".env")

DEBUG = os.environ.get("DEBUG", "False").lower() in ("true", "1", "t")

SECRET_KEY = os.environ.get("SECRET_KEY", "")
if not SECRET_KEY:
    if not DEBUG:
        raise ImproperlyConfigured("SECRET_KEY must be set when DEBUG is False.")
    SECRET_KEY = "django-insecure-marketlink-local-development-only"

ALLOWED_HOSTS = [
    h.strip() for h in os.environ.get("ALLOWED_HOSTS", "localhost,127.0.0.1").split(",") if h.strip()
]

NUM_PROXIES = int(os.environ.get("NUM_PROXIES", "0"))

INSTALLED_APPS = [
    "daphne",
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "rest_framework",
    "rest_framework_simplejwt",
    "corsheaders",
    "drf_spectacular",
    "simple_history",
    "channels",
    "marketlink_core",
    "accounts",
    "markets",
    "catalog",
    "orders",
    "reviews",
    "favorites",
    "notifications",
    "system",
    "chat_bot",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "corsheaders.middleware.CorsMiddleware",
    "marketlink_core.middleware.RequestIDMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
    "simple_history.middleware.HistoryRequestMiddleware",
]

ROOT_URLCONF = "marketlink_core.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [BASE_DIR / "templates"],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
            ],
        },
    },
]

WSGI_APPLICATION = "marketlink_core.wsgi.application"
ASGI_APPLICATION = "marketlink_core.asgi.application"

_db_options = {
    "charset": "utf8mb4",
    "init_command": "SET sql_mode='STRICT_TRANS_TABLES'",
    "isolation_level": "read committed",
}
if os.environ.get("DB_SSL", "False").lower() in ("true", "1", "t"):
    _db_options["ssl"] = {"ssl": {}}

DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.mysql",
        "NAME": os.environ.get("DB_NAME", "marketlink"),
        "USER": os.environ.get("DB_USER", "marketlink_user"),
        "PASSWORD": os.environ.get("DB_PASSWORD", ""),
        "HOST": os.environ.get("DB_HOST", "127.0.0.1"),
        "PORT": os.environ.get("DB_PORT", "3306"),
        "ATOMIC_REQUESTS": False,
        "OPTIONS": _db_options,
        "TEST": {
            "CHARSET": "utf8mb4",
            "COLLATION": "utf8mb4_0900_ai_ci",
        },
        "CONN_MAX_AGE": int(os.environ.get("DB_CONN_MAX_AGE", "0")),
    }
}

AUTH_USER_MODEL = "accounts.CustomUser"
DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

AUTH_PASSWORD_VALIDATORS = [
    {
        "NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"
    },
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator"},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]

LANGUAGE_CODE = "en-us"
TIME_ZONE = "Asia/Ho_Chi_Minh"
USE_I18N = True
USE_TZ = True

STATIC_URL = "/static/"
STATIC_ROOT = BASE_DIR / "staticfiles"

MEDIA_URL = "/media/"
MEDIA_ROOT = BASE_DIR / "media"

REST_FRAMEWORK = {
    "DEFAULT_AUTHENTICATION_CLASSES": [
        "accounts.auth.authentication.SessionJWTAuthentication",
    ],
    "DEFAULT_PERMISSION_CLASSES": [
        "rest_framework.permissions.IsAuthenticated",
    ],
    "DEFAULT_SCHEMA_CLASS": "drf_spectacular.openapi.AutoSchema",
    "DEFAULT_PAGINATION_CLASS": "marketlink_core.pagination.StandardPagination",
    "EXCEPTION_HANDLER": "marketlink_core.responses.custom_exception_handler",
    "PAGE_SIZE": 20,
    "DEFAULT_THROTTLE_CLASSES": [
        "rest_framework.throttling.AnonRateThrottle",
        "rest_framework.throttling.UserRateThrottle",
    ],
    "NUM_PROXIES": NUM_PROXIES,
    "DEFAULT_THROTTLE_RATES": {
        "anon": "120/min",
        "user": "300/min",
        "login": "5/min",
        "admin_login": "5/min",
        "login_email": "20/hour",
        "register": "10/hour",
        "orders": "10/hour",
        "chat": "20/min",
        "geocode": "10/min",
    },
}

SIMPLE_JWT = {
    "ACCESS_TOKEN_LIFETIME": timedelta(minutes=15),
    "REFRESH_TOKEN_LIFETIME": timedelta(days=7),
    "ROTATE_REFRESH_TOKENS": True,
    "BLACKLIST_AFTER_ROTATION": False,
    "AUTH_HEADER_TYPES": ("Bearer",),
    "USER_ID_FIELD": "id",
    "USER_ID_CLAIM": "user_id",
}

CORS_ALLOWED_ORIGINS = [
    "http://localhost:5173",
    "http://127.0.0.1:5173",
    "http://localhost:5174",
    "http://127.0.0.1:5174",
]
_extra_origins = os.environ.get("CORS_ALLOWED_ORIGINS", "")
if _extra_origins:
    CORS_ALLOWED_ORIGINS.extend(
        [o.strip() for o in _extra_origins.split(",") if o.strip()]
    )

CORS_ALLOWED_ORIGIN_REGEXES = [
    r"^https:\/\/.*\.vercel\.app$",
    r"^http:\/\/(localhost|127\.0\.0\.1)(:\d+)?$",
]

CSRF_TRUSTED_ORIGINS = [
    "http://localhost:5173",
    "http://127.0.0.1:5173",
]
_extra_csrf = os.environ.get("CSRF_TRUSTED_ORIGINS", "") or os.environ.get("CORS_ALLOWED_ORIGINS", "")
if _extra_csrf:
    CSRF_TRUSTED_ORIGINS.extend(
        [o.strip() for o in _extra_csrf.split(",") if o.strip()]
    )

CORS_ALLOW_CREDENTIALS = True
CORS_ALLOW_HEADERS = list(default_headers) + [
    "if-match",
    "idempotency-key",
    "x-request-id",
]
CORS_EXPOSE_HEADERS = [
    "x-request-id",
    "content-disposition",
    "idempotent-replayed",
]

X_FRAME_OPTIONS = "DENY"
SECURE_CONTENT_TYPE_NOSNIFF = True

if not DEBUG:
    SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
    SECURE_SSL_REDIRECT = os.environ.get("SECURE_SSL_REDIRECT", "True").lower() in ("true", "1", "t")
    SECURE_REDIRECT_EXEMPT = [r"^api/health/$"]
    SECURE_HSTS_SECONDS = int(os.environ.get("SECURE_HSTS_SECONDS", "3600"))
    SESSION_COOKIE_SECURE = True
    CSRF_COOKIE_SECURE = True

REDIS_URL = os.environ.get("REDIS_URL", "redis://127.0.0.1:6379/0")
USE_REDIS = os.environ.get("USE_REDIS", "False").lower() in ("true", "1", "t")

_REDIS_CACHE_OPTIONS = {
    "CLIENT_CLASS": "django_redis.client.DefaultClient",
    "IGNORE_EXCEPTIONS": True,
    "SOCKET_CONNECT_TIMEOUT": 5,
    "SOCKET_TIMEOUT": 5,
}
if REDIS_URL.startswith("rediss://"):
    _REDIS_CACHE_OPTIONS["CONNECTION_POOL_KWARGS"] = {"ssl_cert_reqs": None}

if USE_REDIS:
    _channel_host = {
        "address": REDIS_URL,
        "socket_connect_timeout": 5,
        "socket_timeout": 10,
        "socket_keepalive": True,
        "health_check_interval": 30,
    }
    if REDIS_URL.startswith("rediss://"):
        _channel_host["ssl_cert_reqs"] = None

    CACHES = {
        "default": {
            "BACKEND": "django_redis.cache.RedisCache",
            "LOCATION": REDIS_URL,
            "KEY_PREFIX": "cache",
            "OPTIONS": _REDIS_CACHE_OPTIONS,
        },
        "blacklist": {
            "BACKEND": "django_redis.cache.RedisCache",
            "LOCATION": REDIS_URL,
            "KEY_PREFIX": "blacklist",
            "OPTIONS": _REDIS_CACHE_OPTIONS,
        },
    }
    CHANNEL_LAYERS = {
        "default": {
            "BACKEND": "channels_redis.core.RedisChannelLayer",
            "CONFIG": {
                "hosts": [_channel_host],
                "prefix": "marketlink",
                "capacity": 1500,
                "expiry": 60,
            },
        },
    }
else:
    CACHES = {
        "default": {"BACKEND": "django.core.cache.backends.locmem.LocMemCache"},
        "blacklist": {
            "BACKEND": "django.core.cache.backends.locmem.LocMemCache",
            "LOCATION": "blacklist",
        },
    }
    CHANNEL_LAYERS = {
        "default": {"BACKEND": "channels.layers.InMemoryChannelLayer"},
    }

WS_TICKET_TTL = int(os.environ.get("WS_TICKET_TTL", "30"))

NOMINATIM_URL = os.environ.get("NOMINATIM_URL") or "https://nominatim.openstreetmap.org/search"
NOMINATIM_USER_AGENT = os.environ.get("NOMINATIM_USER_AGENT") or "MarketLink/1.0 (TechWiz 7 student project)"
GEOCODING_ENABLED = os.environ.get("GEOCODING_ENABLED", "True").lower() in ("true", "1", "t")

EMAIL_HOST_USER = os.environ.get("EMAIL_HOST_USER", "")
EMAIL_HOST_PASSWORD = os.environ.get("EMAIL_HOST_PASSWORD", "")

EMAIL_BACKEND = os.environ.get(
    "EMAIL_BACKEND",
    (
        "django.core.mail.backends.smtp.EmailBackend"
        if EMAIL_HOST_USER
        else "django.core.mail.backends.console.EmailBackend"
    ),
)
EMAIL_HOST = os.environ.get("EMAIL_HOST", "smtp.gmail.com")
EMAIL_PORT = int(os.environ.get("EMAIL_PORT", 587))
EMAIL_USE_TLS = os.environ.get("EMAIL_USE_TLS", "True").lower() in ("true", "1", "t")
DEFAULT_FROM_EMAIL = os.environ.get(
    "DEFAULT_FROM_EMAIL", EMAIL_HOST_USER or "MarketLink <no-reply@marketlink.vn>"
)

SPECTACULAR_SETTINGS = {
    "TITLE": "MarketLink RESTful API",
    "DESCRIPTION": "Connecting local farmers with traditional market shoppers (eGreen Basket) - TechWiz 7",
    "VERSION": "1.0.0",
    "SERVE_INCLUDE_SCHEMA": False,
    "SECURITY": [{"bearerAuth": []}],
    "ENUM_NAME_OVERRIDES": {
        "OrderStatusEnum": "orders.models.OrderStatus.choices",
        "FarmerStatusEnum": "accounts.models.FarmerStatus.choices",
    },
    "COMPONENTS": {
        "securitySchemes": {
            "bearerAuth": {
                "type": "http",
                "scheme": "bearer",
                "bearerFormat": "JWT",
            }
        }
    },
}

GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY", "")
AI_CHAT_ENABLED = os.environ.get("AI_CHAT_ENABLED", "True").lower() in (
    "true",
    "1",
    "t",
)

AI_MODERATION_ENABLED = os.environ.get("AI_MODERATION_ENABLED", "True").lower() in ("true", "1", "t")
AI_AUTO_APPROVE = os.environ.get("AI_AUTO_APPROVE", "True").lower() in ("true", "1", "t")
GEMINI_MODERATION_MODEL = os.environ.get("GEMINI_MODERATION_MODEL", "gemini-3.1-flash-lite")
GEMINI_MODERATION_FALLBACK_MODELS = [
    name.strip()
    for name in os.environ.get(
        "GEMINI_MODERATION_FALLBACK_MODELS", "gemini-3.5-flash-lite"
    ).split(",")
    if name.strip()
]
AI_MODERATION_TIMEOUT_MS = int(os.environ.get("AI_MODERATION_TIMEOUT_MS", "20000"))
AI_MODERATION_BATCH_PAUSE_MS = int(os.environ.get("AI_MODERATION_BATCH_PAUSE_MS", "4000"))
GEMINI_CHAT_MODEL = os.environ.get("GEMINI_CHAT_MODEL", "gemini-3.1-flash-lite")
GEMINI_CHAT_FALLBACK_MODELS = [
    name.strip()
    for name in os.environ.get("GEMINI_CHAT_FALLBACK_MODELS", "gemini-3.5-flash-lite").split(",")
    if name.strip()
]
AI_CHAT_TIMEOUT_MS = int(os.environ.get("AI_CHAT_TIMEOUT_MS", "12000"))
AI_CHAT_DEADLINE_S = float(os.environ.get("AI_CHAT_DEADLINE_S", "15"))
AI_CHAT_DAILY_LIMIT_GUEST = int(os.environ.get("AI_CHAT_DAILY_LIMIT_GUEST", "30"))
AI_CHAT_DAILY_LIMIT_USER = int(os.environ.get("AI_CHAT_DAILY_LIMIT_USER", "100"))
AI_MODERATION_RUN_INLINE = os.environ.get("AI_MODERATION_RUN_INLINE", "False").lower() in ("true", "1", "t")

SIMPLE_HISTORY_HISTORY_CHANGE_REASON_USE_TEXT_FIELD = True

EMAIL_TIMEOUT = int(os.environ.get("EMAIL_TIMEOUT", "10"))
EMAIL_ASYNC = os.environ.get("EMAIL_ASYNC", "True").lower() in ("true", "1", "t")

MAX_PLACED_ORDERS_PER_CUSTOMER = int(os.environ.get("MAX_PLACED_ORDERS_PER_CUSTOMER", "10"))
AT_RISK_THRESHOLD = int(os.environ.get("AT_RISK_THRESHOLD", "3"))
AT_RISK_WINDOW_DAYS = int(os.environ.get("AT_RISK_WINDOW_DAYS", "30"))

LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "handlers": {"console": {"class": "logging.StreamHandler"}},
    "loggers": {
        "marketlink": {"handlers": ["console"], "level": "INFO", "propagate": False},
    },
}
