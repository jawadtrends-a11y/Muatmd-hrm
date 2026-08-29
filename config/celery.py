"""تهيئة Celery — الطوابير الخمسة المعزولة (الوثيقة المعمارية 2)."""
import os
from celery import Celery

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")

app = Celery("muatmd_hrm")
app.config_from_object("django.conf:settings", namespace="CELERY")
app.autodiscover_tasks()

app.conf.task_routes = {
    "apps.notifications.*": {"queue": "realtime"},
    "apps.payroll.*":       {"queue": "payroll"},
    "apps.attendance.*":    {"queue": "attendance"},
    "*.exports.*":          {"queue": "exports"},
}
app.conf.task_default_queue = "maintenance"


@app.task(bind=True)
def debug_task(self):
    return f"Celery يعمل — المهمة {self.request.id}"
