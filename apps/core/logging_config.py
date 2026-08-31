"""
سجل النظام التقني (ق-45).

سطر JSON لكل حدث — يُبحث فيه بـjq بلا أدوات إضافية:
    jq 'select(.level=="ERROR")' logs/app.jsonl
    jq 'select(.duration_ms > 1000)' logs/app.jsonl

لا يخص الشركات ولا يظهر لها. منفصل تمامًا عن سجل عمليات المنشأة.
"""
import json
import logging
import os
import time
import uuid
from datetime import datetime, timezone as dt_timezone

# الحقول التي لا تُكتب — ضجيج أو أسرار
SKIP = {
    "args", "created", "exc_info", "exc_text", "filename", "funcName",
    "levelname", "levelno", "lineno", "module", "msecs", "message",
    "msg", "name", "pathname", "process", "processName", "relativeCreated",
    "stack_info", "thread", "threadName", "taskName",
}

SECRET_HINTS = ("password", "token", "secret", "authorization", "api_key",
                "iban", "id_number")


def _redact(key, value):
    """يحجب الأسرار — السجل يُقرأ من أشخاص كثيرين."""
    if any(h in key.lower() for h in SECRET_HINTS):
        return "***"
    return value


class JsonFormatter(logging.Formatter):
    """سطر JSON لكل حدث."""

    def format(self, record):
        payload = {
            "ts": datetime.now(dt_timezone.utc).isoformat(timespec="milliseconds"),
            "level": record.levelname,
            "logger": record.name,
            "msg": record.getMessage(),
        }
        if record.exc_info:
            payload["exception"] = self.formatException(record.exc_info)

        for key, value in record.__dict__.items():
            if key in SKIP or key.startswith("_"):
                continue
            try:
                json.dumps(value)
                payload[key] = _redact(key, value)
            except (TypeError, ValueError):
                payload[key] = str(value)

        return json.dumps(payload, ensure_ascii=False)


def logging_settings(base_dir, level="INFO"):
    """
    إعداد السجل — يُستدعى من settings.py.

    ملفان: app.jsonl لكل شيء، و errors.jsonl للأخطاء وحدها.
    """
    log_dir = os.path.join(base_dir, "logs")
    os.makedirs(log_dir, exist_ok=True)

    return {
        "version": 1,
        "disable_existing_loggers": False,
        "formatters": {
            "json": {"()": "apps.core.logging_config.JsonFormatter"},
            "plain": {"format": "%(levelname)s %(name)s: %(message)s"},
        },
        "handlers": {
            "console": {
                "class": "logging.StreamHandler",
                "formatter": "plain",
                "level": level,
            },
            "app_file": {
                "class": "logging.handlers.RotatingFileHandler",
                "filename": os.path.join(log_dir, "app.jsonl"),
                "maxBytes": 50 * 1024 * 1024,
                "backupCount": 10,
                "formatter": "json",
                "level": level,
                "encoding": "utf-8",
            },
            "error_file": {
                "class": "logging.handlers.RotatingFileHandler",
                "filename": os.path.join(log_dir, "errors.jsonl"),
                "maxBytes": 50 * 1024 * 1024,
                "backupCount": 10,
                "formatter": "json",
                "level": "WARNING",
                "encoding": "utf-8",
            },
        },
        "loggers": {
            "django.request": {
                "handlers": ["app_file", "error_file", "console"],
                "level": "WARNING",
                "propagate": False,
            },
            "django.security": {
                "handlers": ["error_file", "console"],
                "level": "WARNING",
                "propagate": False,
            },
            "muatmd": {
                "handlers": ["app_file", "error_file", "console"],
                "level": level,
                "propagate": False,
            },
            "celery": {
                "handlers": ["app_file", "error_file"],
                "level": "INFO",
                "propagate": False,
            },
        },
        "root": {"handlers": ["console"], "level": "WARNING"},
    }


# ══════════ وسيط تتبّع الطلبات ══════════

logger = logging.getLogger("muatmd.request")

SLOW_MS = 1000      # عتبة الطلب البطيء


class RequestLogMiddleware:
    """
    يسجّل كل طلب: المسار والحالة والمدة.

    request_id يربط كل سجلات الطلب الواحد — فتتبّع خطأ يعني
    البحث بمعرّف واحد لا بالوقت التقريبي.
    """

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        request_id = uuid.uuid4().hex[:12]
        request.request_id = request_id
        started = time.monotonic()

        response = self.get_response(request)
        duration_ms = int((time.monotonic() - started) * 1000)

        ctx = getattr(request, "account_ctx", None)
        payload = {
            "request_id": request_id,
            "method": request.method,
            "path": request.path,
            "status": response.status_code,
            "duration_ms": duration_ms,
            "account_id": getattr(ctx, "account_id", None),
            "company_id": getattr(ctx, "active_company_id", None),
            "user_id": (request.user.id
                        if getattr(request, "user", None)
                        and request.user.is_authenticated else None),
            "ip": self._client_ip(request),
        }

        if response.status_code >= 500:
            logger.error("request_failed", extra=payload)
        elif response.status_code >= 400:
            logger.warning("request_rejected", extra=payload)
        elif duration_ms >= SLOW_MS:
            logger.warning("request_slow", extra=payload)
        else:
            logger.info("request", extra=payload)

        response["X-Request-ID"] = request_id
        return response

    @staticmethod
    def _client_ip(request):
        forwarded = request.META.get("HTTP_X_FORWARDED_FOR")
        if forwarded:
            return forwarded.split(",")[0].strip()
        return request.META.get("REMOTE_ADDR")
