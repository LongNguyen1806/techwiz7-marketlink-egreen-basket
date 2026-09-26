import os
from datetime import timedelta
from pathlib import Path
from corsheaders.defaults import default_headers
from django.core.exceptions import ImproperlyConfigured
from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent.parent
load_dotenv(BASE_DIR / ".env")

# Fail closed: a deployment that forgets DEBUG runs as production, never as a debug server.
DEBUG = os.environ.get("DEBUG", "False").lower() in ("true", "1", "t")

# The fallback key is only for local development; production must provide its own.
SECRET_KEY = os.environ.get("SECRET_KEY", "")
if not SECRET_KEY:
    if not DEBUG:
        raise ImproperlyConfigured("SECRET_KEY must be set when DEBUG is False.")
    SECRET_KEY = "django-insecure-marketlink-local-development-only"

ALLOWED_HOSTS = [
    h.strip() for h in os.environ.get("ALLOWED_HOSTS", "localhost,127.0.0.1").split(",") if h.strip()
]

# Number of reverse proxies in front of the app (Render: 1). Only the X-Forwarded-For entry
# appended by those proxies is trusted, so a client cannot pick its own IP for throttling or
# the audit log. 0 = no proxy: REMOTE_ADDR is the client.
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

DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.mysql",
        "NAME": os.environ.get("DB_NAME", "marketlink"),
        "USER": os.environ.get("DB_USER", "marketlink_user"),
        "PASSWORD": os.environ.get("DB_PASSWORD", ""),
        "HOST": os.environ.get("DB_HOST", "127.0.0.1"),
        "PORT": os.environ.get("DB_PORT", "3306"),
        "ATOMIC_REQUESTS": False,
        "OPTIONS": {
            "charset": "utf8mb4",
            "init_command": "SET sql_mode='STRICT_TRANS_TABLES'",
            "isolation_level": "read committed",
        },
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
        # Failed sign-ins per email, across every IP and both portals (brute force from many IPs).
        "login_email": "20/hour",
        "register": "10/hour",
        "orders": "10/hour",
        "chat": "20/min",
    },
}

SIMPLE_JWT = {
    "ACCESS_TOKEN_LIFETIME": timedelta(minutes=15),
    "REFRESH_TOKEN_LIFETIME": timedelta(days=7),
    "ROTATE_REFRESH_TOKENS": True,
    # Refresh tokens are blacklisted in Redis by the auth views (P2), not by a MySQL table.
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
    # HTTPS is terminated by the proxy (Render), which reports the original scheme in this header.
    SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
    SECURE_SSL_REDIRECT = os.environ.get("SECURE_SSL_REDIRECT", "True").lower() in ("true", "1", "t")
    # Uptime probes may call the health check over plain HTTP.
    SECURE_REDIRECT_EXEMPT = [r"^api/health/$"]
    SECURE_HSTS_SECONDS = int(os.environ.get("SECURE_HSTS_SECONDS", "3600"))
    SESSION_COOKIE_SECURE = True
    CSRF_COOKIE_SECURE = True

REDIS_URL = os.environ.get("REDIS_URL", "redis://127.0.0.1:6379/0")
USE_REDIS = os.environ.get("USE_REDIS", "False").lower() in ("true", "1", "t")

# Bounded socket waits: a hung Redis must fail fast instead of blocking every authenticated request.
_REDIS_CACHE_OPTIONS = {
    "CLIENT_CLASS": "django_redis.client.DefaultClient",
    "SOCKET_CONNECT_TIMEOUT": 2,
    "SOCKET_TIMEOUT": 2,
}

if USE_REDIS:
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
                "hosts": [
                    {
                        "address": REDIS_URL,
                        "socket_connect_timeout": 5,
                        "socket_keepalive": True,
                        "health_check_interval": 30,
                    }
                ],
                "prefix": "marketlink",
                "capacity": 1500,
                "expiry": 60,
            },
        },
    }
else:
    # Not shared between processes: only for single-process local development.
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

# D-032: farmer coordinates from the address via OpenStreetMap Nominatim (usage policy:
# max 1 request/second and a User-Agent that identifies the app with a contact email).
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

# TEXT, not VARCHAR(100): farmer suspension reasons can be up to 500 characters.
SIMPLE_HISTORY_HISTORY_CHANGE_REASON_USE_TEXT_FIELD = True

EMAIL_TIMEOUT = int(os.environ.get("EMAIL_TIMEOUT", "10"))
EMAIL_ASYNC = os.environ.get("EMAIL_ASYNC", "True").lower() in ("true", "1", "t")

# D-005 / D-028: order and account abuse thresholds.
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
