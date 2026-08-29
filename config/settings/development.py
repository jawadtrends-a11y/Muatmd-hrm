"""إعدادات بيئة التطوير — لا تُستخدم في الإنتاج إطلاقًا."""
from .base import *  # noqa: F401,F403

DEBUG = True
ALLOWED_HOSTS = ["*"]
CORS_ALLOW_ALL_ORIGINS = True

# بريد التطوير يُطبع في السجل بدل الإرسال الفعلي
EMAIL_BACKEND = "django.core.mail.backends.console.EmailBackend"

# تشغيل مهام Celery فورًا عند الحاجة للتشخيص (معطّل افتراضيًا)
CELERY_TASK_ALWAYS_EAGER = False
