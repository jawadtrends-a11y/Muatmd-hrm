"""إعدادات مشتركة بين كل البيئات."""
from pathlib import Path
import environ

BASE_DIR = Path(__file__).resolve().parent.parent.parent

env = environ.Env(DEBUG=(bool, False))
environ.Env.read_env(BASE_DIR / ".env")

SECRET_KEY = env("SECRET_KEY")
DEBUG = env("DEBUG")
ALLOWED_HOSTS = env.list("ALLOWED_HOSTS", default=[])

INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "rest_framework",
    "corsheaders",
    "drf_spectacular",

    # تطبيقات معتمد
    "apps.core",
    "apps.accounts",
    "apps.organization",
    "apps.employees",
    "apps.payroll",
    "apps.attendance",
    "apps.leaves",
    "apps.notifications",
]

MIDDLEWARE = [
    "corsheaders.middleware.CorsMiddleware",
    "django.middleware.security.SecurityMiddleware",
    "whitenoise.middleware.WhiteNoiseMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.locale.LocaleMiddleware",  # يقرأ الكوكي ثم الجلسة
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

ROOT_URLCONF = "config.urls"
WSGI_APPLICATION = "config.wsgi.application"

TEMPLATES = [{
    "BACKEND": "django.template.backends.django.DjangoTemplates",
    "DIRS": [BASE_DIR / "templates"],
    "APP_DIRS": True,
    "OPTIONS": {"context_processors": [
        "django.template.context_processors.request",
        "django.contrib.auth.context_processors.auth",
        "django.contrib.messages.context_processors.messages",
    ]},
}]

# ملاحظة أمنية حاكمة:
# التطبيق يتصل بدور hrm_runtime (NOBYPASSRLS) لا بمالك الجداول.
# مالك الجداول hrm_app خارق ويتجاوز RLS — يُستخدم للهجرات فقط عبر
# متغير البيئة DJANGO_DB_OWNER=1. راجع الوثيقة المعمارية (2).
_USE_OWNER = env.bool("DJANGO_DB_OWNER", default=False)

DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.postgresql",
        "NAME": env("POSTGRES_DB"),
        "USER": env("POSTGRES_USER") if _USE_OWNER else env("POSTGRES_RUNTIME_USER"),
        "PASSWORD": env("POSTGRES_PASSWORD") if _USE_OWNER else env("POSTGRES_RUNTIME_PASSWORD"),
        "HOST": env("POSTGRES_HOST"),
        "PORT": env("POSTGRES_PORT"),
        # يُستخدم في الاختبارات للاتصال بدور التشغيل المحدود
        "TEST_RUNTIME_USER": env("POSTGRES_RUNTIME_USER"),
        "TEST_RUNTIME_PASSWORD": env("POSTGRES_RUNTIME_PASSWORD"),
    }
}

# شرط إلزامي لعمل العزل بـRLS — راجع الوثيقة المعمارية (2)
ATOMIC_REQUESTS = True
DATABASES["default"]["ATOMIC_REQUESTS"] = True

CACHES = {"default": {
    "BACKEND": "django_redis.cache.RedisCache",
    "LOCATION": env("REDIS_URL"),
}}

CELERY_BROKER_URL = env("REDIS_URL")
CELERY_RESULT_BACKEND = env("REDIS_URL")
CELERY_TASK_TRACK_STARTED = True
CELERY_TIMEZONE = env("TIME_ZONE", default="Asia/Riyadh")

AUTH_PASSWORD_VALIDATORS = [
    {"NAME": f"django.contrib.auth.password_validation.{v}"}
    for v in ("UserAttributeSimilarityValidator", "MinimumLengthValidator",
              "CommonPasswordValidator", "NumericPasswordValidator")
]

LANGUAGE_CODE = env("LANGUAGE_CODE", default="ar")
TIME_ZONE = env("TIME_ZONE", default="Asia/Riyadh")
USE_I18N = True
USE_TZ = True

LANGUAGES = [("ar", "العربية"), ("en", "English"), ("ur", "اردو")]
LOCALE_PATHS = [BASE_DIR / "locale"]

STATIC_URL = "static/"
STATIC_ROOT = BASE_DIR / "staticfiles"
MEDIA_URL = "media/"
MEDIA_ROOT = BASE_DIR / "mediafiles"

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

REST_FRAMEWORK = {
    "DEFAULT_SCHEMA_CLASS": "drf_spectacular.openapi.AutoSchema",
    "DEFAULT_AUTHENTICATION_CLASSES": [
        "rest_framework.authentication.SessionAuthentication",
    ],
    "DEFAULT_PERMISSION_CLASSES": ["rest_framework.permissions.IsAuthenticated"],
}

SPECTACULAR_SETTINGS = {
    "TITLE": "معتمد HRM API",
    "VERSION": "0.1.0",
}

# ── اللغة ──────────────────────────────────────────────
# العربية هي الافتراضي. LocaleMiddleware يحترم اختيار المستخدم
# الصريح (كوكي/جلسة) لكنه لا يتبع لغة المتصفح، وإلا ظهرت الواجهة
# بالإنجليزية لمستخدم عربي لمجرد إعداد متصفحه.
LANGUAGE_COOKIE_NAME = "muatmd_lang"
LOCALE_PATHS = [BASE_DIR / "locale"]
